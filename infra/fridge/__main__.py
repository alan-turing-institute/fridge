import pulumi

from pulumi import ResourceOptions
from pulumi_kubernetes.batch.v1 import CronJobPatch, CronJobSpecPatchArgs
from pulumi_kubernetes.core.v1 import NamespacePatch
from pulumi_kubernetes.meta.v1 import ObjectMetaPatchArgs
from pulumi_kubernetes.yaml import ConfigFile

import components
from enums import K8sEnvironment, PodSecurityStandard, TlsEnvironment


def patch_namespace(name: str, pss: PodSecurityStandard) -> NamespacePatch:
    """
    Apply a PodSecurityStandard label to a namespace
    """
    return NamespacePatch(
        f"{name}-ns-pod-security",
        metadata=ObjectMetaPatchArgs(name=name, labels={} | pss.value),
    )


config = pulumi.Config()
tls_environment = TlsEnvironment(config.require("tls_environment"))
stack_name = pulumi.get_stack()

try:
    k8s_environment = K8sEnvironment(config.get("k8s_env"))
except ValueError:
    raise ValueError(
        f"Invalid k8s environment: {config.get('k8s_env')}. "
        f"Supported values are {', '.join([item.value for item in K8sEnvironment])}."
    )

# START hubble
# Hubble UI
# Interface for Cilium
if k8s_environment == K8sEnvironment.AKS:
    hubble_ui = ConfigFile(
        "hubble-ui",
        file="./k8s/hubble/hubble_ui.yaml",
    )
# END

ingress_nginx = components.Ingress(
    "ingress-nginx",
    args=components.IngressArgs(k8s_environment=k8s_environment),
)

cert_manager = components.CertManager(
    "cert-manager",
    args=components.CertManagerArgs(
        config=config,
        k8s_environment=k8s_environment,
        tls_environment=tls_environment,
    ),
)

if k8s_environment == K8sEnvironment.DAWN:
    dawn_managed_namespaces = ["cert-manager", "ingress-nginx"]
    for namespace in dawn_managed_namespaces:
        patch_namespace(namespace, PodSecurityStandard.RESTRICTED)

    # Add label to etcd-defrag jobs to allow Cilium to permit them to communicate with the API server
    # These jobs are installed automatically on DAWN using Helm, and do not otherwise have a consistent label
    # so cannot be selected by Cilium.
    CronJobPatch(
        "etcd-defrag-cronjob-label",
        metadata=ObjectMetaPatchArgs(name="etcd-defrag", namespace="kube-system"),
        spec=CronJobSpecPatchArgs(
            job_template={
                "spec": {"template": {"metadata": {"labels": {"etcd-defrag": "true"}}}}
            }
        ),
    )

# Storage classes
storage_classes = components.StorageClasses(
    "storage_classes",
    components.StorageClassesArgs(
        k8s_environment=k8s_environment,
        azure_disk_encryption_set=(
            config.require("azure_disk_encryption_set")
            if k8s_environment is K8sEnvironment.AKS
            else None
        ),
        azure_resource_group=(
            config.require("azure_resource_group")
            if k8s_environment is K8sEnvironment.AKS
            else None
        ),
        azure_subscription_id=(
            config.require("azure_subscription_id")
            if k8s_environment is K8sEnvironment.AKS
            else None
        ),
    ),
)

# Use patches for standard namespaces rather then trying to create them, so Pulumi does not try to delete them on teardown
standard_namespaces = ["default", "kube-node-lease", "kube-public"]
for namespace in standard_namespaces:
    patch_namespace(namespace, PodSecurityStandard.RESTRICTED)

# Minio
minio = components.ObjectStorage(
    "minio",
    args=components.ObjectStorageArgs(
        config=config,
        tls_environment=tls_environment,
        storage_classes=storage_classes,
    ),
    opts=ResourceOptions(
        depends_on=[
            ingress_nginx,
            cert_manager,
            storage_classes,
        ]
    ),
)

# Argo Workflows
enable_sso = k8s_environment is not K8sEnvironment.K3S

argo_workflows = components.WorkflowServer(
    "argo-workflows",
    args=components.WorkflowServerArgs(
        config=config,
        tls_environment=tls_environment,
        enable_sso=enable_sso,
    ),
    opts=ResourceOptions(
        depends_on=[
            ingress_nginx,
            cert_manager,
        ]
    ),
)

if enable_sso:
    argo_workflows_rbac = components.WorkflowUiRbac(
        "argo-workflows-rbac",
        args=components.WorkflowUiRbacArgs(
            config=config,
            argo_workflows_ns=argo_workflows.argo_workflows_ns,
            argo_server_ns=argo_workflows.argo_server_ns,
        ),
        opts=ResourceOptions(
            depends_on=[argo_workflows],
        ),
    )

# Harbor
harbor = components.ContainerRegistry(
    "harbor",
    components.ContainerRegistryArgs(
        config=config,
        tls_environment=tls_environment,
        storage_classes=storage_classes,
    ),
    opts=ResourceOptions(
        depends_on=[ingress_nginx, cert_manager, storage_classes],
    ),
)


# API Server
api_server = components.ApiServer(
    name=f"{stack_name}-api-server",
    args=components.ApiServerArgs(
        argo_server_ns=argo_workflows.argo_server_ns,
        argo_workflows_ns=argo_workflows.argo_workflows_ns,
        fridge_api_admin=config.require_secret("fridge_api_admin"),
        fridge_api_password=config.require_secret("fridge_api_password"),
        minio_url=minio.minio_cluster_url,
        minio_access_key=config.require_secret("minio_root_user"),
        minio_secret_key=config.require_secret("minio_root_password"),
        verify_tls=tls_environment is TlsEnvironment.PRODUCTION,
    ),
    opts=ResourceOptions(
        depends_on=[argo_workflows],
    ),
)

# Network policy (through Cilium)

# Network policies should be deployed last to ensure that none of them interfere with the deployment process

resources = [
    argo_workflows,
    harbor.configure_containerd_daemonset,
    harbor,
    ingress_nginx,
    minio,
    storage_classes,
]

network_policies = components.NetworkPolicies(
    name=f"{stack_name}-network-policies",
    k8s_environment=k8s_environment,
    opts=ResourceOptions(
        depends_on=resources,
    ),
)

# Pulumi exports
pulumi.export("argo_fqdn", argo_workflows.argo_fqdn)
pulumi.export("harbor_fqdn", harbor.harbor_fqdn)
pulumi.export("minio_fqdn", minio.minio_fqdn)
pulumi.export("ingress_ip", ingress_nginx.ingress_ip)
pulumi.export("ingress_ports", ingress_nginx.ingress_ports)
