from string import Template

import pulumi
from pulumi import Output, ResourceOptions
from pulumi_kubernetes.batch.v1 import CronJobPatch, CronJobSpecPatchArgs
from pulumi_kubernetes.core.v1 import Namespace, NamespacePatch, Secret, ServiceAccount
from pulumi_kubernetes.helm.v3 import Release
from pulumi_kubernetes.helm.v4 import Chart, RepositoryOptsArgs
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs, ObjectMetaPatchArgs
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
argo_workflows = components.WorkflowServer(
    "argo-workflows",
    args=components.WorkflowServerArgs(
        config=config,
        tls_environment=tls_environment,
    ),
    opts=ResourceOptions(
        depends_on=[
            ingress_nginx,
            cert_manager,
            cert_manager_issuers,
        ]
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
        namespace=argo_workflows.argo_workflows_ns,
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
        namespace=argo_workflows.argo_workflows_ns,
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
        namespace=argo_workflows.argo_workflows_ns,
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
        namespace=argo_workflows.argo_workflows_ns,
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
            namespace=argo_workflows.argo_workflows_ns,
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
        namespace=argo_workflows.argo_server_ns,
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
        namespace=argo_workflows.argo_server_ns,
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
    argo_workflows_ns=argo_workflows.argo_workflows_ns,
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
    harbor_fqdn=harbor.harbor_fqdn,
    harbor_url=harbor.harbor_external_url,
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
