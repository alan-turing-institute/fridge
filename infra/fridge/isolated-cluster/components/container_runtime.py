import ssl


import pulumi
from pulumi import ComponentResource, Output, ResourceOptions
from string import Template
from enums import K8sEnvironment, PodSecurityStandard
from pulumi_kubernetes.core.v1 import ConfigMap, Namespace
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs
from pulumi_kubernetes.yaml import ConfigGroup


def get_harbor_cert(harbor_fqdn: str) -> str:
    cert = ssl.get_server_certificate((harbor_fqdn, 443))
    return cert


class ContainerRuntimeConfigArgs:
    def __init__(
        self,
        config: pulumi.config.Config,
        harbor_fqdn: Output[str],
        k8s_environment: K8sEnvironment,
    ) -> None:
        self.config = config
        self.harbor_fqdn = harbor_fqdn
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
                yaml_template = open("k8s/containerd/registry_mirrors.yaml", "r").read()
            case K8sEnvironment.DAWN:
                yaml_template = open("k8s/containerd/dawn_registries.yaml", "r").read()

        # Warning: this means the machine running pulumi up must be able to resolve the harbor FQDN and connect to it on port 443 to retrieve the certificate.
        ca_cert = args.harbor_fqdn.apply(lambda fqdn: get_harbor_cert(fqdn))

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
