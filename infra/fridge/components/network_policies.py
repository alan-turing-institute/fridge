from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.yaml import ConfigFile

from enums import K8sEnvironment


class NetworkPolicies(ComponentResource):
    def __init__(self, name: str, k8s_environment: str, opts=ResourceOptions) -> None:
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

        ConfigFile(
            "network_policy_argo_workflows",
            file="./k8s/cilium/argo_workflows.yaml",
            opts=child_opts,
        )

        ConfigFile(
            "network_policy_argo_server",
            file="./k8s/cilium/argo_server.yaml",
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

        ConfigFile(
            "network_policy_longhorn",
            file="./k8s/cilium/longhorn.yaml",
            opts=child_opts,
        )

        ConfigFile(
            "network_policy_minio_tenant",
            file="./k8s/cilium/minio-tenant.yaml",
            opts=child_opts,
        )

        ConfigFile(
            "network_policy_minio_operator",
            file="./k8s/cilium/minio-operator.yaml",
            opts=child_opts,
        )
