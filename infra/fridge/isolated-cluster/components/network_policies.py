import pulumi
from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.yaml import ConfigFile, ConfigGroup

from enums import K8sEnvironment


class NetworkPoliciesArgs:
    def __init__(
        self,
        config: pulumi.config.Config,
        k8s_environment: K8sEnvironment,
    ):
        self.config = config
        self.k8s_environment = k8s_environment


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
            case K8sEnvironment.DAWN:
                # Dawn uses a different external DNS server to AKS, and also runs regular jobs that do not run on AKS
                ConfigFile(
                    "network_policy_dawn",
                    file="./k8s/cilium/dawn.yaml",
                    opts=child_opts,
                )
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

        self.isolated_general_cnp = ConfigGroup(
            "network_policies",
            files=[
                "./k8s/cilium/argo_server.yaml",
                "./k8s/cilium/argo_workflows.yaml",
                "./k8s/cilium/cert_manager.yaml",
                "./k8s/cilium/fridge_api.yaml",
                "./k8s/cilium/hubble.yaml",
                "./k8s/cilium/kube-node-lease.yaml",
                "./k8s/cilium/kube-public.yaml",
                "./k8s/cilium/kube-system.yaml",
                "./k8s/cilium/minio-tenant.yaml",
                "./k8s/cilium/minio-operator.yaml",
            ],
        )
