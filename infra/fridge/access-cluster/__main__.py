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

# Private API proxy
api_ssh_jumpbox = components.FridgeAPIJumpbox(
    "fridge-api-ssh-jumpbox",
    components.FridgeAPIJumpboxArgs(
        config=config,
        k8s_environment=k8s_environment,
    ),
)

ingress_nginx = components.Ingress(
    "ingress-nginx",
    args=components.IngressArgs(
        api_jumpbox=api_ssh_jumpbox, k8s_environment=k8s_environment
    ),
)

cert_manager = components.CertManager(
    "cert-manager",
    args=components.CertManagerArgs(
        config=config,
        k8s_environment=k8s_environment,
        tls_environment=tls_environment,
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

# Network policy (through Cilium)
# Network policies should be deployed last to ensure that none of them interfere with the deployment process
resources = [
    cert_manager,
    harbor.configure_containerd_daemonset,
    harbor,
    ingress_nginx,
    storage_classes,
]

network_policies = components.NetworkPolicies(
    name=f"{stack_name}-network-policies",
    config=config,
    k8s_environment=k8s_environment,
    opts=ResourceOptions(
        depends_on=resources,
    ),
)

# Pulumi exports
pulumi.export("fridge_api_ip_address", config.require("fridge_api_ip_address"))
pulumi.export("harbor_fqdn", harbor.harbor_fqdn)
pulumi.export("harbor_ip_address", harbor.harbor_lb_ip)
pulumi.export("ingress_ip", ingress_nginx.ingress_ip)
pulumi.export("ingress_ports", ingress_nginx.ingress_ports)
