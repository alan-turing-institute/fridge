import pulumi
from pulumi import ComponentResource, Output, ResourceOptions
from pulumi_kubernetes.core.v1 import Namespace
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs
from pulumi_kubernetes.yaml import ConfigGroup
from string import Template
from enums import PodSecurityStandard


class DNSConfigArgs:
    def __init__(
        self,
        harbor_fqdn: Output[str],
        harbor_ip: Output[str],
    ) -> None:
        self.harbor_fqdn = harbor_fqdn
        self.harbor_ip = harbor_ip


class DNSConfig(ComponentResource):
    def __init__(
        self,
        name: str,
        args: DNSConfigArgs,
        opts: ResourceOptions | None = None,
    ):
        super().__init__("fridge:DNSConfig", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        # Namespace shared with container runtime config; created here on Dawn
        # since ContainerRuntimeConfig (which also creates it) is AKS-only.
        self.config_ns = Namespace(
            "dns-config-ns",
            metadata=ObjectMetaArgs(
                name="containerd-config",
                labels={} | PodSecurityStandard.PRIVILEGED.value,
            ),
            opts=child_opts,
        )

        yaml_template = open("k8s/dnsconfig/node_hosts.yaml", "r").read()

        # Render the DaemonSet template with the harbor FQDN and IP, then deploy it.
        # The DaemonSet writes the harbor entry into /etc/hosts on every node so
        # that containerd (which uses the OS resolver via systemd-resolved) can
        # resolve the harbor FQDN to the internal IP address for image pulls.
        node_hosts_config = Output.all(
            namespace=self.config_ns.metadata.name,
            harbor_fqdn=args.harbor_fqdn,
            harbor_ip=args.harbor_ip,
        ).apply(
            lambda args: Template(yaml_template).substitute(
                namespace=args["namespace"],
                harbor_fqdn=args["harbor_fqdn"],
                harbor_ip=args["harbor_ip"],
            )
        )

        self.configure_node_hosts = node_hosts_config.apply(
            lambda yaml_content: ConfigGroup(
                "configure-node-hosts",
                yaml=[yaml_content],
                opts=ResourceOptions.merge(
                    child_opts,
                    ResourceOptions(
                        depends_on=[self.config_ns],
                    ),
                ),
            )
        )

        self.register_outputs({})
