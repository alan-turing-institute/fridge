import pulumi
from pulumi import ComponentResource, Output, ResourceOptions
from string import Template
from enums import PodSecurityStandard
from pulumi_kubernetes.core.v1 import Namespace
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs
from pulumi_kubernetes.yaml import ConfigGroup


class ContainerRuntimeConfigArgs:
    def __init__(
        self,
        config: pulumi.config.Config,
        harbor_fqdn: Output[str],
    ) -> None:
        self.config = config
        self.harbor_fqdn = harbor_fqdn


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

        yaml_template = open("k8s/containerd/registry_mirrors.yaml", "r").read()

        registry_mirror_config = Output.all(
            namespace=self.config_ns.metadata.name,
            harbor_fqdn=args.harbor_fqdn,
        ).apply(
            lambda args: Template(yaml_template).substitute(
                namespace=args["namespace"],
                harbor_fqdn=args["harbor_fqdn"],
            )
        )

        self.configure_runtime = registry_mirror_config.apply(
            lambda yaml_content: ConfigGroup(
                "configure-container-runtime",
                yaml=[yaml_content],
                opts=ResourceOptions.merge(
                    child_opts,
                    ResourceOptions(
                        depends_on=[self.config_ns],
                    ),
                ),
            )
        )
