import pulumi
from pulumi import ComponentResource, FileAsset, Output, ResourceOptions
from pulumi_kubernetes.core.v1 import Namespace, Secret
from pulumi_kubernetes.helm.v4 import Chart, RepositoryOptsArgs
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs

from enums import PodSecurityStandard, TlsEnvironment, tls_issuer_names


class WorkflowServerArgs:
    def __init__(
        self,
        config: pulumi.config.Config,
        tls_environment: TlsEnvironment,
        enable_sso: bool,
    ):
        self.config = config
        self.tls_environment = tls_environment
        self.enable_sso = enable_sso


class WorkflowServer(ComponentResource):
    def __init__(
        self, name: str, args: WorkflowServerArgs, opts: ResourceOptions | None = None
    ):
        super().__init__("fridge:WorkflowServer", name, None, opts=opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        argo_server_ns = Namespace(
            "argo-server-ns",
            metadata=ObjectMetaArgs(
                name="argo-server",
                labels={} | PodSecurityStandard.RESTRICTED.value,
            ),
            opts=child_opts,
        )

        argo_workflows_ns = Namespace(
            "argo-workflows-ns",
            metadata=ObjectMetaArgs(
                name="argo-workflows",
                labels={} | PodSecurityStandard.RESTRICTED.value,
            ),
            opts=child_opts,
        )

        argo_fqdn = ".".join(
            (
                args.config.require("argo_fqdn_prefix"),
                args.config.require("base_fqdn"),
            )
        )

        argo_server_sso_config = {
            "enabled": args.enable_sso,
        }

        argo_server_auth_modes = [
            "client"
        ]  # Default list is client only, as it is required for the FRIDGE API server

        # if args.enable_sso:
        #     argo_server_sso_config.update(
        #         {
        #             "issuer": args.config.require_secret("sso_issuer_url"),
        #             "redirectUrl": Output.concat(
        #                 "https://", argo_fqdn, "/oauth2/callback"
        #             ),
        #             "scopes": args.config.require_object("argo_scopes"),
        #         }
        #     )
        #     argo_server_auth_modes.append("sso")
        #     argo_sso_secret = Secret(
        #         "argo-server-sso-secret",
        #         metadata=ObjectMetaArgs(
        #             name="argo-server-sso",
        #             namespace=argo_server_ns.metadata.name,
        #         ),
        #         type="Opaque",
        #         string_data={
        #             "client-id": args.config.require_secret("oidc_client_id"),
        #             "client-secret": args.config.require_secret("oidc_client_secret"),
        #         },
        #         opts=ResourceOptions(
        #             depends_on=[argo_server_ns],
        #         ),
        #     )
        # else:
        #     argo_sso_secret = None
        #     argo_server_auth_modes.append(
        #         "server"
        #     )  # Only for non-SSO environments (effectively no auth)

        argo_minio_secret = Secret(
            "argo-minio-secret",
            metadata=ObjectMetaArgs(
                name="argo-artifacts-minio",
                namespace=argo_workflows_ns.metadata.name,
            ),
            type="Opaque",
            string_data={
                "accesskey": args.config.require_secret("minio_root_user"),
                "secretkey": args.config.require_secret("minio_root_password"),
            },
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[argo_server_ns]),
            ),
        )

        argo_depends_on = [
            argo_minio_secret,
            argo_server_ns,
            argo_workflows_ns,
        ]
        # if argo_sso_secret is not None:
        #     argo_depends_on.append(argo_sso_secret)

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
                    "authModes": argo_server_auth_modes,
                    "ingress": {
                        "annotations": {
                            "cert-manager.io/cluster-issuer": tls_issuer_names[
                                args.tls_environment
                            ],
                        },
                        "hosts": [argo_fqdn],
                        "tls": [
                            {
                                "secretName": "argo-ingress-tls-letsencrypt",
                                "hosts": [argo_fqdn],
                            }
                        ],
                    },
                    # "sso": argo_server_sso_config,
                },
            },
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(
                    depends_on=argo_depends_on,
                ),
            ),
        )

        outputs = {
            "argo_workflows": argo_workflows,
            "argo_minio_secret": argo_minio_secret,
            "argo_server_ns": argo_server_ns,
            "argo_workflows_ns": argo_workflows_ns,
        }
        # if argo_sso_secret is not None:
        #     outputs["argo_sso_secret"] = argo_sso_secret

        self.argo_fqdn = argo_fqdn
        self.argo_server_ns = argo_server_ns.metadata.name
        self.argo_workflows_ns = argo_workflows_ns.metadata.name
        self.register_outputs(outputs)
