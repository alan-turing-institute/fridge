import pulumi
from pulumi import ComponentResource, Output, ResourceOptions
from string import Template
from enums import K8sEnvironment, PodSecurityStandard
from pulumi_kubernetes.core.v1 import ConfigMap, Namespace
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs
from pulumi_kubernetes.yaml import ConfigGroup


class ContainerRuntimeConfigArgs:
    def __init__(
        self,
        config: pulumi.config.Config,
        harbor_fqdn: Output[str],
        harbor_ca_cert: Output[str] | Output[None],
        harbor_uses_custom_ca: Output[bool],
        k8s_environment: K8sEnvironment,
    ) -> None:
        self.config = config
        self.harbor_ca_cert = harbor_ca_cert
        self.harbor_fqdn = harbor_fqdn
        self.harbor_uses_custom_ca = harbor_uses_custom_ca
        self.k8s_environment = k8s_environment


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

        match args.k8s_environment:
            case K8sEnvironment.AKS:
                with open("k8s/containerd/registry_mirrors.yaml", "r") as file:
                    yaml_template = file.read()

                def render_template(values: dict[str, str | bool]) -> str:
                    return Template(yaml_template).substitute(
                        namespace=values["namespace"],
                        harbor_fqdn=values["harbor_fqdn"],
                    )

            case K8sEnvironment.DAWN:
                with open("k8s/containerd/dawn_registries.yaml", "r") as file:
                    dawn_production_template = file.read()
                with open("k8s/containerd/dawn_registries_custom_ca.yaml", "r") as file:
                    dawn_custom_ca_template = file.read()

                def render_template(values: dict[str, str | bool]) -> str:
                    template = (
                        dawn_custom_ca_template
                        if values["uses_custom_ca"]
                        else dawn_production_template
                    )
                    return Template(template).substitute(
                        namespace=values["namespace"],
                        harbor_fqdn=values["harbor_fqdn"],
                    )

        # Fix case later when this is None
        # this is also only really necessary on Dawn, and shouldn't be necessary in production

        custom_ca = args.harbor_uses_custom_ca
        ca_cert = custom_ca.apply(
            lambda uses_custom_ca: args.harbor_ca_cert if uses_custom_ca else ""
        )

        self.harbor_cert = ConfigMap(
            "harbor-ca-cert",
            metadata=ObjectMetaArgs(
                namespace=self.config_ns.metadata.name,
                name="harbor-ca-cert",
            ),
            data={
                "harbor_cert.pem": ca_cert,
            },
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[self.config_ns]),
            ),
        )

        registry_mirror_config = Output.all(
            namespace=self.config_ns.metadata.name,
            harbor_fqdn=args.harbor_fqdn,
            uses_custom_ca=args.harbor_uses_custom_ca,
        ).apply(render_template)

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
