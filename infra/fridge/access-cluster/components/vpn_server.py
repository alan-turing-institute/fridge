import pulumi
from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.apps.v1 import Deployment, DeploymentSpecArgs
from pulumi_kubernetes.core.v1 import ConfigMap, Namespace
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs

from enums import PodSecurityStandard, SoftwareVersion


class VpnServerArgs:
    def __init__(self, config: pulumi.config.Config) -> None:
        self.config = config


class VpnServer(ComponentResource):
    def __init__(
        self, name: str, args: VpnServerArgs, opts: ResourceOptions | None = None
    ) -> None:
        super().__init__("fridge:fridge-access-cluster:VpnServer", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        self.vpn_ns = Namespace(
            "vpn-ns",
            metadata=ObjectMetaArgs(
                name="vpn-server",
                labels={} | PodSecurityStandard.PRIVILEGED.value,
            ),
            opts=child_opts,
        )

        self.haproxy_config = ConfigMap(
            "haproxy-config",
            metadata=ObjectMetaArgs(
                namespace=self.vpn_ns.metadata.name,
                name="vpn-proxy-config",
            ),
            data={
                "haproxy.cfg": """

global
  log stdout format raw local0

defaults
  mode tcp
  timeout connect 30s
  timeout client 3600s
  timeout server 3600s

frontend fridge_api_in
    bind *:8000
    default_backend fridge_api_out

backend fridge_api_out
    server fridge_api 10.20.1.60:443 check
""",
            },
        )

        self.vpn_deployment = Deployment(
            "netbird-proxy",
            metadata=ObjectMetaArgs(
                namespace=self.vpn_ns.metadata.name,
            ),
            spec=DeploymentSpecArgs(
                selector={"matchLabels": {"app": "netbird-proxy"}},
                replicas=1,
                template={
                    "metadata": {
                        "labels": {"app": "netbird-proxy"},
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": "netbird-proxy",
                                "image": "netbirdio/netbird:latest",
                                "env": [
                                    {
                                        "name": "NB_SETUP_KEY",
                                        "value": args.config.require_secret(
                                            "netbird_setup_key"
                                        ),
                                    },
                                ],
                                "volumeMounts": [
                                    {
                                        "name": "netbird-data",
                                        "mountPath": "/var/lib/netbird",
                                    },
                                ],
                                "securityContext": {
                                    "capabilities": {
                                        "add": [
                                            "NET_ADMIN",
                                            "SYS_RESOURCE",
                                            "SYS_ADMIN",
                                        ]
                                    },
                                },
                            },
                            {
                                "name": "haproxy",
                                "image": f"haproxy:{SoftwareVersion.HAPROXY.value}",
                                "ports": [{"containerPort": 8000, "protocol": "TCP"}],
                                "volumeMounts": [
                                    {
                                        "name": "haproxy-config",
                                        "mountPath": "/usr/local/etc/haproxy/haproxy.cfg",
                                        "subPath": "haproxy.cfg",
                                    },
                                ],
                            },
                        ],
                        "volumes": [
                            {
                                "name": "netbird-data",
                                "emptyDir": {},
                            },
                            {
                                "name": "haproxy-config",
                                "configMap": {
                                    "name": self.haproxy_config.metadata.name
                                },
                            },
                        ],
                    },
                },
            ),
            opts=child_opts,
        )
