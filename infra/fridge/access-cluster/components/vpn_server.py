import pulumi
from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.apps.v1 import Deployment, DeploymentSpecArgs
from pulumi_kubernetes.core.v1 import ConfigMap, Namespace
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs

from enums import PodSecurityStandard


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

        vpn_proxy_config = ConfigMap(
            "vpn-proxy-config",
            metadata=ObjectMetaArgs(
                namespace=self.vpn_ns.metadata.name,
                name="vpn-proxy-config",
            ),
            data={
                "nginx.conf": """
worker_processes auto;

events {
  worker_connections 1024;
}

stream {
  upstream private_dns_server {
    # Private API server FQDN:53
    server kube-dns.kube-system.svc.cluster.local:53;
  }

  server {
    # TCP listener inside the pod
    listen 8443;

    # Timeouts suitable for long-lived kubectl streams
    proxy_connect_timeout 30s;
    proxy_timeout 3600s;

    # Pure TCP passthrough to the upstream
    proxy_pass private_dns_server;

    proxy_ssl_server_name on;
    proxy_ssl_verify off;
    proxy_ssl_trusted_certificate /etc/nginx/conf.d/certs/api/certificate;
  }
}
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
                        # "hostNetwork": True,
                        # "dnsPolicy": "ClusterFirstWithHostNet",
                        "containers": [
                            {
                                "name": "netbird-proxy",
                                "image": "netbirdio/netbird:latest",
                                "env": [
                                    {
                                        "name": "NB_SETUP_KEY",
                                        "value": "AB27FECF-F4EC-4D43-82BE-B108609F871F",
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
                            # {
                            #     "name": "nginx-proxy",
                            #     "image": "nginx:latest",
                            #     "ports": [
                            #         {"containerPort": 8443, "protocol": "TCP"}
                            #     ],
                            #     "volumeMounts": [
                            #         {
                            #             "name": "vpn-proxy-config",
                            #             "mountPath": "/etc/nginx/nginx.conf",
                            #             "subPath": "nginx.conf",
                            #         },
                            #     ],
                            # },
                        ],
                        "volumes": [
                            {
                                "name": "netbird-data",
                                "emptyDir": {},
                            },
                            {
                                "name": "vpn-proxy-config",
                                "configMap": {"name": vpn_proxy_config.metadata.name},
                            },
                        ],
                    },
                },
            ),
            opts=child_opts,
        )
