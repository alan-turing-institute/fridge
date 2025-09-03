from string import Template

import pulumi

from pulumi import ResourceOptions
from pulumi_kubernetes.batch.v1 import CronJobPatch, CronJobSpecPatchArgs
from pulumi_kubernetes.core.v1 import Namespace, NamespacePatch
from pulumi_kubernetes.helm.v3 import Release
from pulumi_kubernetes.helm.v4 import Chart, RepositoryOptsArgs
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs, ObjectMetaPatchArgs

from pulumi_kubernetes.yaml import ConfigFile, ConfigGroup

import components
from enums import K8sEnvironment, PodSecurityStandard, TlsEnvironment, tls_issuer_names


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

# Hubble UI
# Interface for Cilium
if k8s_environment == K8sEnvironment.AKS:
    hubble_ui = ConfigFile(
        "hubble-ui",
        file="./k8s/hubble/hubble_ui.yaml",
    )

match k8s_environment:
    case K8sEnvironment.AKS | K8sEnvironment.K3S:
        # Ingress NGINX (ingress provider)
        ingress_nginx_ns = Namespace(
            "ingress-nginx-ns",
            metadata=ObjectMetaArgs(
                name="ingress-nginx",
                labels={} | PodSecurityStandard.RESTRICTED.value,
            ),
        )

        ingress_nginx = ConfigFile(
            "ingress-nginx",
            file="https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.12.1/deploy/static/provider/cloud/deploy.yaml",
            opts=ResourceOptions(
                depends_on=[ingress_nginx_ns],
            ),
        )

        # CertManager (TLS automation)
        cert_manager_ns = Namespace(
            "cert-manager-ns",
            metadata=ObjectMetaArgs(
                name="cert-manager",
                labels={} | PodSecurityStandard.RESTRICTED.value,
            ),
        )

        cert_manager = Chart(
            "cert-manager",
            namespace=cert_manager_ns.metadata.name,
            chart="cert-manager",
            version="1.17.1",
            repository_opts=RepositoryOptsArgs(
                repo="https://charts.jetstack.io",
            ),
            values={
                "crds": {"enabled": True},
                "extraArgs": ["--acme-http01-solver-nameservers=8.8.8.8:53,1.1.1.1:53"],
            },
            opts=ResourceOptions(
                depends_on=[cert_manager_ns],
            ),
        )
        # Get public IP address and ports of Ingress Nginx loadbalancer service
        # Note that this relies on Ingress-Nginx being installed as for AKS
        # On Dawn it is installed using a Helm chart and has different properties.
        pulumi.export(
            "ingress_ip",
            ingress_nginx.resources["v1/Service:ingress-nginx/ingress-nginx-controller"]
            .status.load_balancer.ingress[0]
            .ip,
        )
        pulumi.export(
            "ingress_ports",
            ingress_nginx.resources[
                "v1/Service:ingress-nginx/ingress-nginx-controller"
            ].spec.ports.apply(lambda ports: [item.port for item in ports]),
        )

    case K8sEnvironment.DAWN:
        dawn_managed_namespaces = ["cert-manager", "ingress-nginx"]
        cert_manager_ns = Namespace.get("cert-manager-ns", "cert-manager")
        ingress_nginx_ns = Namespace.get("ingress-nginx-ns", "ingress-nginx")
        for namespace in dawn_managed_namespaces:
            patch_namespace(namespace, PodSecurityStandard.RESTRICTED)
        cert_manager = Release.get("cert-manager", "cert-manager")
        ingress_nginx = Release.get("ingress-nginx", "ingress-nginx")

        # Add label to etcd-defrag jobs to allow Cilium to permit them to communicate with the API server
        # These jobs are installed automatically on DAWN using Helm, and do not otherwise have a consistent label
        # so cannot be selected by Cilium.
        CronJobPatch(
            "etcd-defrag-cronjob-label",
            metadata=ObjectMetaPatchArgs(name="etcd-defrag", namespace="kube-system"),
            spec=CronJobSpecPatchArgs(
                job_template={
                    "spec": {
                        "template": {"metadata": {"labels": {"etcd-defrag": "true"}}}
                    }
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

cluster_issuer_config = Template(
    open("k8s/cert_manager/clusterissuer.yaml", "r").read()
).substitute(
    lets_encrypt_email=config.require("lets_encrypt_email"),
    issuer_name_staging=tls_issuer_names[TlsEnvironment.STAGING],
    issuer_name_production=tls_issuer_names[TlsEnvironment.PRODUCTION],
)

cert_manager_issuers = ConfigGroup(
    "cert-manager-issuers",
    yaml=[cluster_issuer_config],
    opts=ResourceOptions(
        depends_on=[cert_manager, cert_manager_ns],
    ),
)

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
            cert_manager_issuers,
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
            cert_manager_issuers,
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
        depends_on=[ingress_nginx, cert_manager, cert_manager_issuers, storage_classes],
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
