import base64
from enum import Enum, verify, UNIQUE
from string import Template

import pulumi
from pulumi import FileAsset, Output, ResourceOptions
from pulumi_azure_native import containerservice, managedidentity, resources
import pulumi_tls as tls
import pulumi_kubernetes as kubernetes
from pulumi_kubernetes.core.v1 import (
    Namespace,
    Secret,
    ServiceAccount,
)

from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs
from pulumi_kubernetes.helm.v4 import Chart, RepositoryOptsArgs
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs
from pulumi_kubernetes.networking.v1 import Ingress
from pulumi_kubernetes.storage.v1 import StorageClass
from pulumi_kubernetes.yaml import ConfigFile, ConfigGroup
from pulumi_kubernetes.rbac.v1 import (
    PolicyRuleArgs,
    Role,
    RoleBinding,
    RoleRefArgs,
    SubjectArgs,
)


@verify(UNIQUE)
class TlsEnvironment(Enum):
    STAGING = "staging"
    PRODUCTION = "production"


def get_kubeconfig(
    credentials: list[containerservice.outputs.CredentialResultResponse],
) -> str:
    for credential in credentials:
        if credential.name == "clusterAdmin":
            return base64.b64decode(credential.value).decode()


config = pulumi.Config()

tls_environment = TlsEnvironment(config.require("tls_environment"))
tls_issuer_names = {
    TlsEnvironment.STAGING: "letsencrypt-staging",
    TlsEnvironment.PRODUCTION: "letsencrypt-prod",
}

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
    config.require("cluster_name"),
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
        network_dataplane=containerservice.NetworkDataplane.CILIUM,
        network_plugin=containerservice.NetworkPlugin.AZURE,
        network_policy=containerservice.NetworkPolicy.CILIUM,
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

minio_url = Output.format(
    "{0}.{1}",
    config.require("minio_url_prefix"),
    config.require("base_fqdn"),
)
minio_config_env = Output.format(
    (
        "export MINIO_BROWSER_REDIRECT_URL=https://{0}\n"
        "export MINIO_SERVER_URL=http://minio.argo-artifacts.svc.cluster.local\n"
        "export MINIO_ROOT_USER={1}\n"
        "export MINIO_ROOT_PASSWORD={2}"
    ),
    minio_url,
    config.require_secret("minio_root_user"),
    config.require_secret("minio_root_password"),
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
                "requestAutoCert": "false",
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
                    "console": minio_url,
                    "minio": [
                        Output.concat(minio_url, "/api"),
                        "minio.argo-artifacts.svc.cluster.local",
                    ],
                }
            },
            "pools": [
                {
                    "servers": 1,
                    "name": "argo-artifacts-pool-0",
                    "size": config.require("minio_pool_size"),
                    "volumesPerServer": 1,
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
            "nginx.ingress.kubernetes.io/force-ssl-redirect": "true",
            "cert-manager.io/cluster-issuer": tls_issuer_names[tls_environment],
        },
    ),
    spec={
        "ingress_class_name": "nginx",
        "tls": [
            {
                "hosts": [
                    minio_url,
                ],
                "secret_name": "argo-artifacts-tls",
            }
        ],
        "rules": [
            {
                "host": minio_url,
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

# Argo Workflows
argo_server_ns = Namespace(
    "argo-server-ns",
    metadata=ObjectMetaArgs(
        name="argo-server",
    ),
    opts=ResourceOptions(
        provider=k8s_provider,
        depends_on=[managed_cluster],
    ),
)

argo_workflows_ns = Namespace(
    "argo-workflows-ns",
    metadata=ObjectMetaArgs(
        name="argo-workflows",
    ),
    opts=ResourceOptions(
        provider=k8s_provider,
        depends_on=[managed_cluster],
    ),
)

argo_url = Output.concat(
    config.require("argo_url_prefix"),
    ".",
    config.require("base_fqdn"),
)

argo_sso_secret = Secret(
    "argo-server-sso-secret",
    metadata=ObjectMetaArgs(
        name="argo-server-sso",
        namespace=argo_server_ns.metadata.name,
    ),
    type="Opaque",
    string_data={
        "client-id": config.require_secret("oidc_client_id"),
        "client-secret": config.require_secret("oidc_client_secret"),
    },
    opts=ResourceOptions(
        provider=k8s_provider,
        depends_on=[argo_server_ns],
    ),
)

argo_minio_secret = Secret(
    "argo-minio-secret",
    metadata=ObjectMetaArgs(
        name="argo-artifacts-minio",
        namespace=argo_workflows_ns.metadata.name,
    ),
    type="Opaque",
    string_data={
        "accesskey": config.require_secret("minio_root_user"),
        "secretkey": config.require_secret("minio_root_password"),
    },
    opts=ResourceOptions(
        provider=k8s_provider,
        depends_on=[argo_server_ns],
    ),
)

argo_workflows = Chart(
    "argo-workflows",
    namespace=argo_server_ns.metadata.name,
    chart="argo-workflows",
    version="0.45.12",
    repository_opts=RepositoryOptsArgs(
        repo="https://argoproj.github.io/argo-helm",
    ),
    value_yaml_files=[
        FileAsset("./k8s/argo_workflows/values.yaml"),
    ],
    values={
        "controller": {"workflowNamespaces": [argo_workflows_ns.metadata.name]},
        "server": {
            "ingress": {
                "annotations": {
                    "cert-manager.io/cluster-issuer": tls_issuer_names[tls_environment],
                },
                "hosts": [argo_url],
                "tls": [
                    {
                        "secretName": "argo-ingress-tls-letsencrypt",
                        "hosts": [argo_url],
                    }
                ],
            },
            "sso": {
                "enabled": True,
                "issuer": config.require_secret("sso_issuer_url"),
                "redirectUrl": Output.concat("https://", argo_url, "/oauth2/callback"),
                "scopes": config.require_object("argo_scopes"),
            },
        },
    },
    opts=ResourceOptions(
        provider=k8s_provider,
        depends_on=[
            argo_minio_secret,
            argo_sso_secret,
            argo_server_ns,
            argo_workflows_ns,
        ],
    ),
)

# Define argo workflows service accounts and roles
# See https://argo-workflows.readthedocs.io/en/latest/security/
# The admin service account gives users in the admin entra group
# permission to run workflows in the Argo Workflows namespace

argo_workflows_admin_role = Role(
    "argo-workflows-admin-role",
    metadata=ObjectMetaArgs(
        name="argo-workflows-admin-role",
        namespace=argo_workflows_ns.metadata.name,
    ),
    rules=[
        PolicyRuleArgs(
            api_groups=[""],
            resources=["events", "pods", "pods/log"],
            verbs=["get", "list", "watch"],
        ),
        PolicyRuleArgs(
            api_groups=["argoproj.io"],
            resources=[
                "cronworkflows",
                "eventsources",
                "workflows",
                "workflows/finalizers",
                "workflowtaskresults",
                "workflowtemplates",
                "clusterworkflowtemplates",
            ],
            verbs=[
                "create",
                "delete",
                "deletecollection",
                "get",
                "list",
                "patch",
                "watch",
                "update",
            ],
        ),
    ],
    opts=ResourceOptions(
        provider=k8s_provider,
        depends_on=[argo_workflows],
    ),
)

argo_workflows_admin_sa = ServiceAccount(
    "argo-workflows-admin-sa",
    metadata=ObjectMetaArgs(
        name="argo-workflows-admin-sa",
        namespace=argo_workflows_ns.metadata.name,
        annotations={
            "workflows.argoproj.io/rbac-rule": Output.concat(
                "'", config.require_secret("oidc_admin_group_id"), "'", " in groups"
            ),
            "workflows.argoproj.io/rbac-rule-precedence": "2",
        },
    ),
    opts=ResourceOptions(
        provider=k8s_provider,
        depends_on=[argo_workflows],
    ),
)

argo_workflows_admin_sa_token = Secret(
    "argo-workflows-admin-sa-token",
    metadata=ObjectMetaArgs(
        name="argo-workflows-admin-sa.service-account-token",
        namespace=argo_workflows_ns.metadata.name,
        annotations={
            "kubernetes.io/service-account.name": argo_workflows_admin_sa.metadata.name,
        },
    ),
    type="kubernetes.io/service-account-token",
    opts=ResourceOptions(
        provider=k8s_provider,
        depends_on=[argo_workflows_admin_sa],
    ),
)

argo_workflows_admin_role_binding = RoleBinding(
    "argo-workflows-admin-role-binding",
    metadata=ObjectMetaArgs(
        name="argo-workflows-admin-role-binding",
        namespace=argo_workflows_ns.metadata.name,
    ),
    role_ref=RoleRefArgs(
        api_group="rbac.authorization.k8s.io",
        kind="Role",
        name=argo_workflows_admin_role.metadata.name,
    ),
    subjects=[
        SubjectArgs(
            kind="ServiceAccount",
            name=argo_workflows_admin_sa.metadata.name,
            namespace=argo_workflows_ns.metadata.name,
        )
    ],
    opts=ResourceOptions(
        provider=k8s_provider,
        depends_on=[argo_workflows_admin_role],
    ),
)

# The admin service account above does not give permission to access the server workspace,
# so the default service account below allows them to get sufficient access to use the UI
# without being able to run workflows in the server namespace

argo_workflows_default_sa = ServiceAccount(
    "argo-workflows-default-sa",
    metadata=ObjectMetaArgs(
        name="user-default-login",
        namespace=argo_server_ns.metadata.name,
        annotations={
            "workflows.argoproj.io/rbac-rule": "true",
            "workflows.argoproj.io/rbac-rule-precedence": "0",
        },
    ),
    opts=ResourceOptions(
        provider=k8s_provider,
        depends_on=[argo_workflows],
    ),
)

argo_workflows_default_sa_token = Secret(
    "argo-workflows-default-sa-token",
    metadata=ObjectMetaArgs(
        name="user-default-login.service-account-token",
        namespace=argo_server_ns.metadata.name,
        annotations={
            "kubernetes.io/service-account.name": argo_workflows_default_sa.metadata.name,
        },
    ),
    type="kubernetes.io/service-account-token",
    opts=ResourceOptions(
        provider=k8s_provider,
        depends_on=[argo_workflows_default_sa],
    ),
)

# Harbor
harbor_ns = Namespace(
    "harbor-ns",
    metadata=ObjectMetaArgs(
        name="harbor",
    ),
    opts=ResourceOptions(
        provider=k8s_provider,
        depends_on=[managed_cluster],
    ),
)

harbor_fqdn = config.require("harbor_url_prefix") + "." + config.require("base_fqdn")

harbor = Release(
    "harbor",
    ReleaseArgs(
        chart="harbor",
        namespace="harbor",
        version="1.16.2",
        repository_opts=RepositoryOptsArgs(
            repo="https://helm.goharbor.io",
        ),
        value_yaml_files=[FileAsset("./k8s/harbor/values.yaml")],
        values={
            "expose": {
                "clusterIP": {
                    "staticClusterIP": config.require("harbor_ip"),
                }
            },
            "externalURL": "https://" + harbor_fqdn,
            "harborAdminPassword": config.require_secret("harbor_admin_password"),
        },
    ),
    opts=ResourceOptions(
        provider=k8s_provider,
        depends_on=[managed_cluster],
    ),
)

# Create a daemonset to skip TLS verification for the harbor registry
# This is needed while using staging/self-signed certificates for Harbor
# A daemonset is used to run the configuration on all nodes in the cluster

skip_harbor_tls = Template(
    open("k8s/harbor/skip_harbor_tls_verification.yaml", "r").read()
).substitute(
    harbor_fqdn=harbor_fqdn,
    harbor_url="https://" + harbor_fqdn,
    harbor_ip=config.require("harbor_ip"),
    harbor_ip_url="http://" + config.require("harbor_ip"),
)

configure_containerd = ConfigGroup(
    "configure-containerd-daemon",
    yaml=[skip_harbor_tls],
    opts=ResourceOptions(
        provider=k8s_provider,
        depends_on=[managed_cluster],
    ),
)

harbor_ingress = Ingress(
    "harbor-ingress",
    metadata=ObjectMetaArgs(
        name="harbor-ingress",
        namespace=harbor_ns.metadata.name,
        annotations={
            "nginx.ingress.kubernetes.io/force-ssl-redirect": "true",
            "nginx.ingress.kubernetes.io/proxy-body-size": "0",
            "cert-manager.io/cluster-issuer": tls_issuer_names[tls_environment],
            "cert-manager.io/ip-sans": config.require("harbor_ip"),
        },
    ),
    spec={
        "ingress_class_name": "nginx",
        "tls": [
            {
                "hosts": [
                    harbor_fqdn,
                ],
                "secret_name": "harbor-ingress-tls",
            }
        ],
        "rules": [
            {
                "host": harbor_fqdn,
                "http": {
                    "paths": [
                        {
                            "path": "/",
                            "path_type": "Prefix",
                            "backend": {
                                "service": {
                                    "name": "harbor",
                                    "port": {
                                        "number": 80,
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
        depends_on=[harbor, harbor_ns],
    ),
)
