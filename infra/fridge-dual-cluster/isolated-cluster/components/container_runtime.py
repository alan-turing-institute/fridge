import pulumi
from pulumi import ComponentResource, ResourceOptions
from string import Template
from enums import PodSecurityStandard
from pulumi_kubernetes.core.v1 import Namespace
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs
from pulumi_kubernetes.yaml import ConfigGroup


class ContainerRuntimeConfigArgs:
    def __init__(
        self,
        config: pulumi.config.Config,
        harbor_ip: str,
    ) -> None:
        self.config = config
        self.harbor_ip = harbor_ip


class ContainerRuntimeConfig(ComponentResource):
    def __init__(
        self,
        name: str,
        args: ContainerRuntimeConfigArgs,
        opts: ResourceOptions | None = None,
    ):
        super().__init__("fridge:ContainerRuntimeConfig", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        self.config_ns = Namespace(
            "container-runtime-config-ns",
            metadata=ObjectMetaArgs(
                name="containerd-config",
                labels={} | PodSecurityStandard.PRIVILEGED.value,
            ),
            opts=child_opts,
        )

        registry_mirror_config = Template(
            open("k8s/containerd/registry_mirrors.yaml", "r").read()
        ).substitute(
            namespace=self.config_ns.metadata.name,
            harbor_ip=args.harbor_ip,
        )

        self.configure_runtime = ConfigGroup(
            "configure-container-runtime",
            files={
                "registry_mirrors.yaml": registry_mirror_config,
            },
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(
                    depends_on=[self.config_ns],
                ),
            ),
        )
