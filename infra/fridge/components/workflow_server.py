import pulumi


class WorkflowServer(ComponentResource):
    def __init__(
        self, name: str, args: WorkflowServerArgs, opts: ResourceOptions = None
    ):
        super().__init__(name, "fridge:WorkflowServer", props=vars(args), opts=opts)


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
