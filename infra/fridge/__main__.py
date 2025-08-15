from string import Template

import pulumi
from pulumi import FileAsset, Output, ResourceOptions
from pulumi_kubernetes.batch.v1 import CronJobPatch, CronJobSpecPatchArgs
from pulumi_kubernetes.core.v1 import Namespace, NamespacePatch, Secret, ServiceAccount
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs
from pulumi_kubernetes.helm.v4 import Chart, RepositoryOptsArgs
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs, ObjectMetaPatchArgs
from pulumi_kubernetes.networking.v1 import Ingress
from pulumi_kubernetes.rbac.v1 import (
    PolicyRuleArgs,
    Role,
    RoleBinding,
    RoleRefArgs,
    SubjectArgs,
)
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
        f"Invalid k8s environment: {k8s_environment}. "
        "Supported values are 'AKS' and 'Dawn'."
    )

match k8s_environment:
    case K8sEnvironment.AKS:
        # Hubble UI
        # Interface for Cilium
        hubble_ui = ConfigFile(
            "hubble-ui",
            file="./k8s/hubble/hubble_ui.yaml",
        )

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
minio_operator_ns = Namespace(
    "minio-operator-ns",
    metadata=ObjectMetaArgs(
        name="minio-operator",
        labels={} | PodSecurityStandard.RESTRICTED.value,
    ),
)

minio_operator = Chart(
    "minio-operator",
    namespace=minio_operator_ns.metadata.name,
    chart="operator",
    repository_opts=RepositoryOptsArgs(
        repo="https://operator.min.io",
    ),
    version="7.1.1",
    opts=ResourceOptions(
        depends_on=[minio_operator_ns],
    ),
)

minio_tenant_ns = Namespace(
    "minio-tenant-ns",
    metadata=ObjectMetaArgs(
        name="argo-artifacts",
        labels={} | PodSecurityStandard.RESTRICTED.value,
    ),
)

minio_fqdn = ".".join(
    (
        config.require("minio_fqdn_prefix"),
        config.require("base_fqdn"),
    )
)
pulumi.export("minio_fqdn", minio_fqdn)

minio_config_env = Output.format(
    (
        "export MINIO_BROWSER_REDIRECT_URL=https://{0}\n"
        "export MINIO_SERVER_URL=http://minio.argo-artifacts.svc.cluster.local\n"
        "export MINIO_ROOT_USER={1}\n"
        "export MINIO_ROOT_PASSWORD={2}"
    ),
    minio_fqdn,
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
        depends_on=[minio_tenant_ns],
    ),
)

minio_tenant = Chart(
    "minio-tenant",
    namespace=minio_tenant_ns.metadata.name,
    chart="tenant",
    name="argo-artifacts",
    version="7.1.1",
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
                    "console": minio_fqdn,
                    "minio": [
                        Output.concat(minio_fqdn, "/api"),
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
                    "storageClassName": storage_classes.encrypted_storage_class.metadata.name,
                    "containerSecurityContext": {
                        "runAsUser": 1000,
                        "runAsGroup": 1000,
                        "runAsNonRoot": True,
                        "allowPrivilegeEscalation": False,
                        "capabilities": {"drop": ["ALL"]},
                        "seccompProfile": {
                            "type": "RuntimeDefault",
                        },
                    },
                },
            ],
        },
    },
    opts=ResourceOptions(
        depends_on=[storage_classes, minio_env_secret, minio_operator, minio_tenant_ns],
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
                    minio_fqdn,
                ],
                "secret_name": "argo-artifacts-tls",
            }
        ],
        "rules": [
            {
                "host": minio_fqdn,
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
        depends_on=[minio_tenant],
    ),
)

# Argo Workflows
argo_server_ns = Namespace(
    "argo-server-ns",
    metadata=ObjectMetaArgs(
        name="argo-server",
        labels={} | PodSecurityStandard.RESTRICTED.value,
    ),
)

argo_workflows_ns = Namespace(
    "argo-workflows-ns",
    metadata=ObjectMetaArgs(
        name="argo-workflows",
        labels={} | PodSecurityStandard.RESTRICTED.value,
    ),
)

argo_fqdn = ".".join(
    (
        config.require("argo_fqdn_prefix"),
        config.require("base_fqdn"),
    )
)
pulumi.export("argo_fqdn", argo_fqdn)

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
                "hosts": [argo_fqdn],
                "tls": [
                    {
                        "secretName": "argo-ingress-tls-letsencrypt",
                        "hosts": [argo_fqdn],
                    }
                ],
            },
            "sso": {
                "enabled": True,
                "issuer": config.require_secret("sso_issuer_url"),
                "redirectUrl": Output.concat("https://", argo_fqdn, "/oauth2/callback"),
                "scopes": config.require_object("argo_scopes"),
            },
        },
    },
    opts=ResourceOptions(
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
        depends_on=[argo_workflows_default_sa],
    ),
)

api_rbac = components.ApiRbac(
    name=f"{stack_name}-api-rbac",
    argo_workflows_ns=argo_workflows_ns.metadata.name,
    opts=ResourceOptions(
        depends_on=[argo_workflows_ns],
    ),
)

# Harbor
harbor_ns = Namespace(
    "harbor-ns",
    metadata=ObjectMetaArgs(
        name="harbor",
        labels={} | PodSecurityStandard.RESTRICTED.value,
    ),
)

harbor_fqdn = ".".join(
    (
        config.require("harbor_fqdn_prefix"),
        config.require("base_fqdn"),
    )
)

f"{config.require('harbor_fqdn_prefix')}.{config.require('base_fqdn')}"
pulumi.export("harbor_fqdn", harbor_fqdn)
harbor_external_url = f"https://{harbor_fqdn}"

harbor = Release(
    "harbor",
    ReleaseArgs(
        chart="harbor",
        namespace="harbor",
        version="1.17.1",
        repository_opts=RepositoryOptsArgs(
            repo="https://helm.goharbor.io",
        ),
        values={
            "expose": {
                "clusterIP": {
                    "staticClusterIP": config.require("harbor_ip"),
                },
                "type": "clusterIP",
                "tls": {
                    "enabled": False,
                    "certSource": "none",
                },
            },
            "externalURL": harbor_external_url,
            "harborAdminPassword": config.require_secret("harbor_admin_password"),
            "persistence": {
                "persistentVolumeClaim": {
                    "registry": {
                        "storageClass": storage_classes.rwm_class_name,
                        "accessMode": "ReadWriteMany",
                    },
                    "jobservice": {
                        "jobLog": {
                            "storageClass": storage_classes.rwm_class_name,
                            "accessMode": "ReadWriteMany",
                        }
                    },
                },
            },
        },
    ),
    opts=ResourceOptions(
        depends_on=[harbor_ns, storage_classes],
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
        depends_on=[harbor],
    ),
)

# Create a daemonset to skip TLS verification for the harbor registry
# This is needed while using staging/self-signed certificates for Harbor
# A daemonset is used to run the configuration on all nodes in the cluster

containerd_config_ns = Namespace(
    "containerd-config-ns",
    metadata=ObjectMetaArgs(
        name="containerd-config",
        labels={} | PodSecurityStandard.PRIVILEGED.value,
    ),
    opts=ResourceOptions(
        depends_on=[harbor],
    ),
)

skip_harbor_tls = Template(
    open("k8s/harbor/skip_harbor_tls_verification.yaml", "r").read()
).substitute(
    namespace="containerd-config",
    harbor_fqdn=harbor_fqdn,
    harbor_url=harbor_external_url,
    harbor_ip=config.require("harbor_ip"),
    harbor_internal_url="http://" + config.require("harbor_ip"),
)

configure_containerd_daemonset = ConfigGroup(
    "configure-containerd-daemon",
    yaml=[skip_harbor_tls],
    opts=ResourceOptions(
        depends_on=[harbor],
    ),
)

# Network policy (through Cilium)

# Network policies should be deployed last to ensure that none of them interfere with the deployment process

resources = [
    argo_workflows,
    configure_containerd_daemonset,
    harbor,
    ingress_nginx,
    minio_ingress,
    minio_operator,
    minio_tenant,
    storage_classes,
]

network_policies = components.NetworkPolicies(
    name=f"{stack_name}-network-policies",
    k8s_environment=k8s_environment,
    opts=ResourceOptions(
        depends_on=resources,
    ),
)
