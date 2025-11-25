import pulumi
from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.apiextensions import CustomResource
from pulumi_kubernetes.yaml import ConfigFile

from enums import K8sEnvironment


class NetworkPolicies(ComponentResource):
    def __init__(
        self,
        config: pulumi.config.Config,
        name: str,
        k8s_environment: K8sEnvironment,
        opts: ResourceOptions | None = None,
    ) -> None:
        super().__init__("fridge:k8s:NetworkPolicies", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        match k8s_environment:
            case K8sEnvironment.AKS:
                # AKS uses Konnectivity to mediate some API/webhook traffic, and uses a different external DNS server
                ConfigFile(
                    "network_policy_aks",
                    file="./k8s/cilium/aks.yaml",
                    opts=child_opts,
                )
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
            case K8sEnvironment.K3S:
                # K3S policies applicable for a local dev environment
                # These could be used in any vanilla k8s + Cilium local cluster
                ConfigFile(
                    "network_policy_k3s",
                    file="./k8s/cilium/k3s.yaml",
                    opts=child_opts,
                )

        self.api_jumpbox_cnp = CustomResource(
            "network_policy_api_jumpbox",
            api_version="cilium.io/v2",
            kind="CiliumNetworkPolicy",
            metadata={"name": "api-jumpbox-access", "namespace": "api-jumpbox"},
            spec={
                "endpointSelector": {"matchLabels": {"app": "api-jumpbox"}},
                "ingress": [
                    {
                        "fromEndpoints": [
                            {
                                "matchLabels": {
                                    "k8s:app.kubernetes.io/name": "ingress-nginx",
                                    "k8s:app.kubernetes.io/component": "controller",
                                    "k8s:io.kubernetes.pod.namespace": "ingress-nginx",
                                }
                            }
                        ],
                        "toPorts": [{"ports": [{"port": "2222", "protocol": "ANY"}]}],
                    }
                ],
                "egress": [
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
                                "rules": {"dns": [{"matchPattern": "*"}]},
                            }
                        ],
                    },
                    {
                        "toEndpoints": [
                            {
                                "matchLabels": {
                                    "k8s:app.kubernetes.io/name": "ingress-nginx",
                                    "k8s:app.kubernetes.io/component": "controller",
                                    "k8s:io.kubernetes.pod.namespace": "ingress-nginx",
                                }
                            }
                        ],
                        "toPorts": [{"ports": [{"port": "2222", "protocol": "TCP"}]}],
                    },
                    {
                        "toCIDR": [config.require("fridge_api_ip_address")],
                        "toPorts": [{"ports": [{"port": "443", "protocol": "TCP"}]}],
                    },
                    {
                        "toFQDNs": [
                            {
                                "matchName": config.require(
                                    "isolated_cluster_api_endpoint"
                                )
                            }
                        ],
                        "toPorts": [{"ports": [{"port": "443", "protocol": "ANY"}]}],
                    },
                ],
            },
            opts=child_opts,
        )

        ConfigFile(
            "network_policy_cert_manager",
            file="./k8s/cilium/cert_manager.yaml",
            opts=child_opts,
        )

        ConfigFile(
            "network_policy_containerd_config",
            file="./k8s/cilium/containerd_config.yaml",
            opts=child_opts,
        )

        ConfigFile(
            "network_policy_harbor",
            file="./k8s/cilium/harbor.yaml",
            opts=child_opts,
        )

        ConfigFile(
            "network_policy_hubble",
            file="./k8s/cilium/hubble.yaml",
            opts=child_opts,
        )

        ConfigFile(
            "network_policy_ingress_nginx",
            file="./k8s/cilium/ingress-nginx.yaml",
            opts=child_opts,
        )

        ConfigFile(
            "network_policy_kube_node_lease",
            file="./k8s/cilium/kube-node-lease.yaml",
            opts=child_opts,
        )

        ConfigFile(
            "network_policy_kube_public",
            file="./k8s/cilium/kube-public.yaml",
            opts=child_opts,
        )

        ConfigFile(
            "network_policy_kubernetes_system",
            file="./k8s/cilium/kube-system.yaml",
            opts=child_opts,
        )
