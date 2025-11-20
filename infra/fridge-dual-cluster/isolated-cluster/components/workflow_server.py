import pulumi
from pulumi import ComponentResource, FileAsset, Output, ResourceOptions
from pulumi_kubernetes.core.v1 import Namespace, Secret
from pulumi_kubernetes.helm.v4 import Chart, RepositoryOptsArgs
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs

from enums import PodSecurityStandard, TlsEnvironment


class WorkflowServerArgs:
    def __init__(
        self,
        config: pulumi.config.Config,
        tls_environment: TlsEnvironment,
    ):
        self.config = config
        self.tls_environment = tls_environment


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

        argo_server_auth_modes = [
            "client",
            "server",
        ]

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

        self.argo_server_ns = argo_server_ns.metadata.name
        self.argo_workflows_ns = argo_workflows_ns.metadata.name
        self.register_outputs(outputs)
