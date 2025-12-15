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

# Hubble UI
# Interface for Cilium
if k8s_environment == K8sEnvironment.AKS:
    hubble_ui = ConfigFile(
        "hubble-ui",
        file="./k8s/hubble/hubble_ui.yaml",
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
            cert_manager,
            storage_classes,
        ]
    ),
)

minio_config = components.MinioConfigJob(
    "minio-config-job",
    args=components.MinioConfigArgs(
        minio_cluster_url=minio.minio_cluster_url,
        minio_credentials={
            "minio_root_user": config.require_secret("minio_root_user"),
            "minio_root_password": config.require_secret("minio_root_password"),
        },
        minio_tenant_ns=minio.minio_tenant_ns,
        minio_tenant=minio.minio_tenant,
    ),
    opts=ResourceOptions(
        depends_on=[minio],
    ),
)


# Argo Workflows
argo_workflows = components.WorkflowServer(
    "argo-workflows",
    args=components.WorkflowServerArgs(
        config=config,
        tls_environment=tls_environment,
    ),
    opts=ResourceOptions(
        depends_on=[
            cert_manager,
        ]
    ),
)

# Set up monitoring
monitoring_system = components.Monitoring(
    name=f"{stack_name}-monitoring-system",
    args=components.MonitoringArgs(
        k8s_environment=k8s_environment,
        argo_server_ns=argo_workflows.argo_server_ns,
    ),
    opts=ResourceOptions(
        depends_on=[
            argo_workflows,
            cert_manager,
            minio,
            storage_classes,
        ],
    ),
)

# Block storage for Argo Workflow jobs
block_storage = components.BlockStorage(
    "block-storage",
    components.BlockStorageArgs(
        config=config,
        storage_classes=storage_classes,
        storage_volume_claim_ns=argo_workflows.argo_workflows_ns,
    ),
    opts=ResourceOptions(
        depends_on=[storage_classes],
    ),
)

argo_workflow_templates = ConfigFile(
    "argo-workflow-templates",
    file="./k8s/argo_workflows/templates.yaml",
    transformations=[
        lambda obj, opts: (
            obj["spec"]["templates"][0]["volumes"][0].update(
                {
                    "persistentVolumeClaim": {
                        "claimName": block_storage.block_storage_pvc
                    }
                }
            )
            if obj["spec"]["templates"][0]["volumes"][0].get("name")
            == "workflow-data-ingress"
            else None
        ),
    ],
    opts=ResourceOptions(
        depends_on=[argo_workflows, block_storage],
    ),
)

# API Server
api_server = components.ApiServer(
    name=f"{stack_name}-api-server",
    args=components.ApiServerArgs(
        argo_server_ns=argo_workflows.argo_server_ns,
        argo_workflows_ns=argo_workflows.argo_workflows_ns,
        config=config,
        minio_url=minio.minio_cluster_url,
        minio_tenant_name=minio.minio_tenant_name,
        verify_tls=tls_environment is TlsEnvironment.PRODUCTION,
    ),
    opts=ResourceOptions(
        depends_on=[argo_workflows],
    ),
)

# Network policy (through Cilium)
# Network policies should be deployed last to ensure that none of them interfere with the deployment process
resources = [
    api_server,
    argo_workflows,
    block_storage,
    minio,
    minio_config,
    storage_classes,
]

network_policies = components.NetworkPolicies(
    name=f"{stack_name}-network-policies",
    k8s_environment=k8s_environment,
    opts=ResourceOptions(
        depends_on=resources,
    ),
)

# Pulumi stack outputs
pulumi.export("fridge_api_ip", config.require("fridge_api_ip"))
