from urllib.parse import urlparse

import pulumi
from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.apiextensions import CustomResource
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs
from pulumi_kubernetes.yaml import ConfigFile, ConfigGroup

from enums import K8sEnvironment


class NetworkPoliciesArgs:
    def __init__(
        self,
        config: pulumi.config.Config,
        harbor_fqdn: str,
        k8s_environment: K8sEnvironment,
    ):
        self.config = config
        self.k8s_environment = k8s_environment
        self.harbor_fqdn = harbor_fqdn


class NetworkPolicies(ComponentResource):
    def __init__(
        self,
        name: str,
        args: NetworkPoliciesArgs,
        opts: ResourceOptions | None = None,
    ) -> None:
        super().__init__("fridge:k8s:NetworkPolicies", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        match args.k8s_environment:
            case K8sEnvironment.AKS:
                # AKS uses Konnectivity to mediate some API/webhook traffic, and uses a different external DNS server
                ConfigFile(
                    "network_policy_aks",
                    file="./k8s/cilium/aks.yaml",
                    opts=child_opts,
                )
                k8s_api_port = "443"
                k8s_api_endpoint_rule = {
                    "toFQDNs": [
                        {
                            "matchName": args.config.require(
                                "isolated_cluster_api_endpoint"
                            )
                        }
                    ],
                    "toPorts": [{"ports": [{"port": k8s_api_port, "protocol": "TCP"}]}],
                }
                fridge_api_ip_rule = {
                    "toCIDR": [args.config.require("fridge_api_ip_address")],
                    "toPorts": [{"ports": [{"port": "443", "protocol": "TCP"}]}],
                }
            case K8sEnvironment.DAWN:
                # Dawn uses a different external DNS server to AKS, and also runs regular jobs that do not run on AKS
                ConfigFile(
                    "network_policy_dawn",
                    file="./k8s/cilium/dawn.yaml",
                    opts=child_opts,
                )
                # Add network policy to allow Prometheus monitoring for resources already deployed on Dawn
                # On Dawn, Prometheus is also already deployed
                ConfigFile(
                    "network_policy_prometheus",
                    file="./k8s/cilium/prometheus.yaml",
                    opts=child_opts,
                )
                # Longhorn is used on Dawn for RWX volume provision
                ConfigFile(
                    "network_policy_longhorn",
                    file="./k8s/cilium/longhorn.yaml",
                    opts=child_opts,
                )
                k8s_api_port = "6443"
                k8s_api_endpoint_rule = {
                    "toCIDR": [args.config.require("isolated_cluster_api_endpoint")],
                    "toPorts": [{"ports": [{"port": k8s_api_port, "protocol": "TCP"}]}],
                }
                fridge_api_ip_rule = {
                    "toCIDR": [
                        "10.20.0.0/16"
                    ],  # [args.config.require("fridge_api_ip_address")],
                    "toPorts": [{"ports": [{"port": "30180", "protocol": "TCP"}]}],
                }
            case K8sEnvironment.K3S:
                # K3S policies applicable for a local dev environment
                # These could be used in any vanilla k8s + Cilium local cluster
                ConfigFile(
                    "network_policy_k3s",
                    file="./k8s/cilium/k3s.yaml",
                    opts=child_opts,
                )

        self.cert_manager_to_harbor = CustomResource(
            "network_policy_cert_manager_to_harbor",
            api_version="cilium.io/v2",
            kind="CiliumNetworkPolicy",
            metadata=ObjectMetaArgs(
                name="cert-manager-to-harbor", namespace="cert-manager"
            ),
            spec={
                "endpointSelector": {"matchLabels": {"app": "cert-manager"}},
                "egress": [
                    {
                        "toEndpoints": [
                            {
                                "matchLabels": {
                                    "k8s-app": "k8s-dns",
                                    "k8s:io.kubernetes.pod.namespace": "kube-system",
                                }
                            },
                        ],
                        "toPorts": [
                            {
                                "ports": [{"port": "53", "protocol": "ANY"}],
                                "rules": {"dns": [{"matchName": args.harbor_fqdn}]},
                            }
                        ],
                    },
                    {
                        "toFQDNs": [
                            {
                                "matchName": args.harbor_fqdn,
                            }
                        ]
                    },
                ],
            },
            opts=child_opts,
        )

        self.access_general_cnp = ConfigGroup(
            "network_policies",
            files=[
                "./k8s/cilium/cert_manager.yaml",
                "./k8s/cilium/containerd_config.yaml",
                "./k8s/cilium/harbor.yaml",
                "./k8s/cilium/hubble.yaml",
                "./k8s/cilium/ingress-nginx.yaml",
                "./k8s/cilium/kube-node-lease.yaml",
                "./k8s/cilium/kube-public.yaml",
                "./k8s/cilium/kube-system.yaml",
            ],
        )

        # Configure NetBird network policies
        netbird_config = args.config.require_object("netbird")
        management_url = urlparse(netbird_config.get("management_url")).hostname
        if not management_url:
            raise ValueError(
                "Invalid management_url in Netbird configuration: must be a valid URL"
            )

        is_cloud_netbird = management_url == "api.netbird.io"

        default_hosts = (
            {
                "signal": "signal.netbird.io",
                "stun": "stun.netbird.io",
                "relay": "relay.netbird.io",
                "turn": "turn.netbird.io",
            }
            if is_cloud_netbird
            else {
                "signal": management_url,
                "stun": management_url,
                "relay": management_url,
                "turn": management_url,
            }
        )

        overrides = netbird_config.get("endpoint_overrides", {})
        netbird_hosts = (
            default_hosts | overrides
        )  # Merge default hosts with any overrides provided in the config

        netbird_dns_rules = [
            {"matchName": management_url},
            {"matchName": netbird_hosts["signal"]},
            {"matchName": netbird_hosts["stun"]},
            {"matchName": netbird_hosts["relay"]},
            {"matchName": netbird_hosts["turn"]},
            {"matchPattern": f"*.{netbird_hosts['relay']}"},
            {"matchPattern": "*.vpn-server.svc.cluster.local"},
        ]

        netbird_egress_rules = [
            {
                "toEndpoints": [
                    {
                        "matchLabels": {
                            "k8s:io.kubernetes.pod.namespace": "kube-system",
                            "k8s-app": "kube-dns",
                        }
                    }
                ],
                "toPorts": [
                    {
                        "ports": [{"port": "53", "protocol": "ANY"}],
                        "rules": {"dns": netbird_dns_rules},
                    }
                ],
            },
            {
                "toFQDNs": [
                    {"matchName": management_url},
                    {"matchName": netbird_hosts["signal"]},
                    {"matchName": netbird_hosts["relay"]},
                    {"matchPattern": f"*.{netbird_hosts['relay']}"},
                ],
                "toPorts": [{"ports": [{"port": "443", "protocol": "TCP"}]}],
            },
            {
                "toFQDNs": [{"matchName": netbird_hosts["stun"]}],
                "toPorts": [
                    {
                        "ports": [
                            {"port": "80", "protocol": "UDP"},
                            {"port": "443", "protocol": "UDP"},
                            {"port": "3478", "protocol": "UDP"},
                            {"port": "5555", "protocol": "UDP"},
                        ]
                    }
                ],
            },
            {
                "toFQDNs": [{"matchName": netbird_hosts["turn"]}],
                "toPorts": [
                    {
                        "ports": [
                            {"port": "80", "protocol": "UDP"},
                            {"port": "443", "protocol": "UDP"},
                            {"port": "443", "endPort": 65535, "protocol": "TCP"},
                        ]
                    }
                ],
            },
        ]

        if args.k8s_environment == K8sEnvironment.AKS:
            netbird_dns_rules.append(
                {"matchName": args.config.require("isolated_cluster_api_endpoint")}
            )

        self.vpn_server_cnp_custom = CustomResource(
            "network_policy_vpn_server_custom",
            api_version="cilium.io/v2",
            kind="CiliumNetworkPolicy",
            metadata=ObjectMetaArgs(name="vpn-server-custom", namespace="vpn-server"),
            spec={
                "endpointSelector": {"matchLabels": {"app": "netbird-proxy"}},
                "egress": netbird_egress_rules
                + [
                    fridge_api_ip_rule,
                    k8s_api_endpoint_rule,
                ],
            },
            opts=child_opts,
        )
