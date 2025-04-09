import base64

import pulumi
from pulumi import ResourceOptions
from pulumi_azure_native import containerservice, managedidentity, resources
from pulumi import Output
import pulumi_tls as tls
import pulumi_kubernetes as kubernetes
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs
from pulumi_kubernetes.core.v1 import (
    Namespace,
    PersistentVolumeClaim,
    PersistentVolumeClaimSpecArgs,
    Secret,
)
from pulumi_kubernetes.yaml import ConfigFile
from pulumi_kubernetes.helm.v4 import Chart, RepositoryOptsArgs
from pulumi_kubernetes.networking.v1 import Ingress
from pulumi_kubernetes.storage.v1 import StorageClass


def get_kubeconfig(
    credentials: list[containerservice.outputs.CredentialResultResponse],
) -> str:
    for credential in credentials:
        if credential.name == "clusterAdmin":
            return base64.b64decode(credential.value).decode()


config = pulumi.Config()

resource_group = resources.ResourceGroup(
    "resource_group",
    resource_group_name=config.require("resource_group_name"),
)

ssh_key = tls.PrivateKey("ssh-key", algorithm="RSA", rsa_bits="3072")

identity = managedidentity.UserAssignedIdentity(
    "cluster_managed_identity",
    resource_group_name=resource_group.name,
)

# AKS cluster
managed_cluster = containerservice.ManagedCluster(
    "cluster",
    resource_group_name=resource_group.name,
    agent_pool_profiles=[
        containerservice.ManagedClusterAgentPoolProfileArgs(
            enable_auto_scaling=True,
            max_count=5,
            max_pods=100,
            min_count=3,
            mode="System",
            name="gppool",
            node_labels={
                "context": "fridge",
                "size": "B4als_v2",
                "arch": "x86_64",
            },
            os_disk_size_gb=0,  # when == 0 sets default size
            os_type="Linux",
            os_sku="Ubuntu",
            type="VirtualMachineScaleSets",
            vm_size="Standard_B4als_v2",
        ),
        containerservice.ManagedClusterAgentPoolProfileArgs(
            enable_auto_scaling=True,
            max_count=5,
            max_pods=100,
            min_count=2,
            mode="System",
            name="systempool",
            node_labels={
                "context": "fridge",
                "size": "B2als_v2",
                "arch": "x86_64",
            },
            os_disk_size_gb=0,  # when == 0 sets default size
            os_type="Linux",
            os_sku="Ubuntu",
            type="VirtualMachineScaleSets",
            vm_size="Standard_B2als_v2",
        ),
    ],
    dns_prefix="fridge",
    identity=containerservice.ManagedClusterIdentityArgs(
        type=containerservice.ResourceIdentityType.USER_ASSIGNED,
        user_assigned_identities=[identity.id],
    ),
    kubernetes_version="1.32",
    linux_profile=containerservice.ContainerServiceLinuxProfileArgs(
        admin_username="fridgeadmin",
        ssh=containerservice.ContainerServiceSshConfigurationArgs(
            public_keys=[
                containerservice.ContainerServiceSshPublicKeyArgs(
                    key_data=ssh_key.public_key_openssh,
                )
            ],
        ),
    ),
    network_profile=containerservice.ContainerServiceNetworkProfileArgs(
        network_dataplane="cilium",
        network_plugin="azure",
        network_policy="cilium",
    ),
    opts=pulumi.ResourceOptions(replace_on_changes=["agent_pool_profiles"]),
)

admin_credentials = containerservice.list_managed_cluster_admin_credentials_output(
    resource_group_name=resource_group.name, resource_name=managed_cluster.name
)

kubeconfig = admin_credentials.kubeconfigs.apply(get_kubeconfig)
pulumi.export(
    "kubeconfig",
    kubeconfig,
)

# Kubernetes configuration
k8s_provider = kubernetes.Provider(
    "k8s_provider",
    kubeconfig=kubeconfig,
)

# Longhorn
longhorn_ns = Namespace(
    "longhorn-system",
    metadata=ObjectMetaArgs(
        name="longhorn-system",
    ),
    opts=ResourceOptions(
        provider=k8s_provider,
        depends_on=[managed_cluster],
    ),
)
longhorn = Chart(
    "longhorn",
    namespace=longhorn_ns.metadata.name,
    chart="longhorn",
    version="1.8.1",
    repository_opts=RepositoryOptsArgs(
        repo="https://charts.longhorn.io",
    ),
    opts=ResourceOptions(
        provider=k8s_provider,
        depends_on=[managed_cluster],
    ),
)

longhorn_storage_class = StorageClass(
    "longhorn-storage",
    allow_volume_expansion=True,
    metadata=ObjectMetaArgs(
        name="longhorn-storage",
    ),
    parameters={
        "dataLocality": "best-effort",
        "fsType": "ext4",
        "numberOfReplicas": "2",
        "staleReplicaTimeout": "2880",
    },
    provisioner="driver.longhorn.io",
    opts=ResourceOptions(
        provider=k8s_provider,
        depends_on=[longhorn],
    ),
)


# Ingress NGINX (ingress provider)
ingress_nginx_ns = Namespace(
    "ingress-nginx-ns",
    metadata=ObjectMetaArgs(
        name="ingress-nginx",
    ),
    opts=ResourceOptions(
        provider=k8s_provider,
        depends_on=[managed_cluster],
    ),
)

ingress_nginx = ConfigFile(
    "ingress-nginx",
    file="https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.12.1/deploy/static/provider/cloud/deploy.yaml",
    opts=ResourceOptions(
        provider=k8s_provider,
        depends_on=[ingress_nginx_ns, managed_cluster],
    ),
)

# CertManager (TLS automation)
cert_manager_ns = Namespace(
    "cert-manager-ns",
    metadata=ObjectMetaArgs(
        name="cert-manager",
    ),
    opts=ResourceOptions(
        provider=k8s_provider,
        depends_on=[managed_cluster],
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
    values={"crds": {"enabled": True}},
    opts=ResourceOptions(
        provider=k8s_provider,
        depends_on=[cert_manager_ns, managed_cluster],
    ),
)

cert_manager_issuers = ConfigFile(
    "cert-manager-issuers",
    file="./k8s/cert_manager/clusterissuer.yaml",
    opts=ResourceOptions(
        provider=k8s_provider,
        depends_on=[cert_manager, cert_manager_ns, managed_cluster],
    ),
)

# Minio
minio_operator_ns = Namespace(
    "minio-operator-ns",
    metadata=ObjectMetaArgs(
        name="minio-operator",
    ),
    opts=ResourceOptions(
        provider=k8s_provider,
        depends_on=[managed_cluster],
    ),
)

minio_operator = Chart(
    "minio-operator",
    namespace=minio_operator_ns.metadata.name,
    chart="operator",
    repository_opts=RepositoryOptsArgs(
        repo="https://operator.min.io",
    ),
    version="7.0.1",
    opts=ResourceOptions(
        provider=k8s_provider,
        depends_on=[minio_operator_ns, managed_cluster],
    ),
)

minio_tenant_ns = Namespace(
    "minio-tenant-ns",
    metadata=ObjectMetaArgs(
        name="argo-artifacts",
    ),
    opts=ResourceOptions(
        provider=k8s_provider,
        depends_on=[managed_cluster],
    ),
)

minio_config_env = Output.all(
    config.require("minio_root_user"), config.require_secret("minio_root_password")
).apply(
    lambda args:
    f"export MINIO_BROWSER_REDIRECT_URL=https://{config.require('minio_browser_url')}/\n "
    f"export MINIO_ROOT_USER={args[0]}\n "
    f"export MINIO_ROOT_PASSWORD={args[1]}\n "
    f"export MINIO_SERVER_URL=http://minio.argo-artifacts.svc.cluster.local"
)

minio_env_secret = Secret(
    "minio-env-secret",
    metadata=ObjectMetaArgs(
        name="argo-artifacts-env-configuration",
        namespace=minio_tenant_ns.metadata.name,
    ),
    type="Opaque",
    string_data={
        "config.env": minio_config_env,
    },
    opts=ResourceOptions(
        provider=k8s_provider,
        depends_on=[minio_tenant_ns],
    ),
)

minio_tenant = Chart(
    "minio-tenant",
    namespace=minio_tenant_ns.metadata.name,
    chart="tenant",
    name="argo-artifacts",
    version="7.0.1",
    repository_opts=RepositoryOptsArgs(
        repo="https://operator.min.io",
    ),
    values={
        "tenant": {
            "name": "argo-artifacts",
            "buckets": [
                {"name": "argo-artifacts"},
            ],
            "certificate": {
                "requestAutoCert" : "false",
            },
            "configuration": {
                "name": "argo-artifacts-env-configuration",
            },
            "configSecret": {
                "name": "argo-artifacts-env-configuration",
                "accessKey": None,
                "secretKey": None,
                "existingSecret": "true",
            },
            "features": {
                "domains": {
                    "console": config.require("minio_browser_url"),
                    "minio": [
                        "minio.fridge.develop.turingsafehaven.ac.uk/api",
                        "minio.argo-artifacts.svc.cluster.local",
                    ],
                }
            },
            "pools": [
                {
                    "servers": 2,
                    "name": "argo-artifacts-pool-0",
                    "size": "20Gi",
                    "volumesPerServer": 2,
                    "storageClassName": longhorn_storage_class.metadata.name,
                },
            ],
        },
    },
    opts=ResourceOptions(
        provider=k8s_provider,
        depends_on=[minio_env_secret, minio_operator, minio_tenant_ns, managed_cluster],
    ),
)

minio_ingress = Ingress(
    "minio-ingress",
    metadata=ObjectMetaArgs(
        name="minio-ingress",
        namespace=minio_tenant_ns.metadata.name,
        annotations={
            "nginx.ingress.kubernetes.io/proxy-body-size": "0",
            "cert-manager.io/cluster-issuer": "letsencrypt-staging",
        },
    ),
    spec={
        "ingress_class_name": "nginx",
        "tls": [
            {
                "hosts": [
                    config.require("minio_browser_url"),
                ],
                "secret_name": "argo-artifacts-tls",
            }
        ],
        "rules": [
            {
                "host": config.require("minio_browser_url"),
                "http": {
                    "paths": [
                        {
                            "path": "/",
                            "path_type": "Prefix",
                            "backend": {
                                "service": {
                                    "name": "argo-artifacts-console",
                                    "port": {
                                        "number": 9090,
                                    },
                                }
                            },
                        }
                    ]
                },
            }
        ],
    },
    opts=ResourceOptions(
        provider=k8s_provider,
        depends_on=[minio_tenant],
    ),
)
