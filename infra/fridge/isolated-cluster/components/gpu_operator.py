import pulumi
from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.core.v1 import Namespace
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs
from pulumi_kubernetes.helm.v4 import RepositoryOptsArgs
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs
from pulumi_kubernetes.yaml import ConfigFile

from enums import K8sEnvironment


class GPUOperatorArgs:
    def __init__(
        self,
        config: pulumi.config.Config,
        k8s_environment: K8sEnvironment,
    ) -> None:
        self.config = config
        self.k8s_environment = k8s_environment


class GPUOperator(ComponentResource):
    def __init__(
        self, name: str, args: GPUOperatorArgs, opts: ResourceOptions | None = None
    ) -> None:
        super().__init__("fridge:k8s:GPUOperator", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        self.node_feature_discovery_ns = Namespace(
            "node-feature-discovery-ns",
            metadata=ObjectMetaArgs(
                name="node-feature-discovery",
            ),
            opts=child_opts,
        )

        self.node_feature_discovery = Release(
            "node-feature-discovery",
            ReleaseArgs(
                name="node-feature-discovery",
                namespace=self.node_feature_discovery_ns.metadata.name,
                chart="node-feature-discovery",
                version="0.18.3",
                repository_opts=RepositoryOptsArgs(
                    repo="https://kubernetes-sigs.github.io/node-feature-discovery/charts",
                ),
            ),
            opts=child_opts,
        )

        if args.k8s_environment == K8sEnvironment.DAWN:

            self.intel_node_feature_rules = ConfigFile(
                "intel-node-feature-rules",
                file="https://raw.githubusercontent.com/intel/intel-device-plugins-for-kubernetes/main/deployments/nfd/overlays/node-feature-rules/node-feature-rules.yaml",
                opts=ResourceOptions.merge(
                    child_opts, ResourceOptions(depends_on=self.node_feature_discovery)
                ),
            )

            self.gpu_operator_ns = Namespace(
                "gpu-operator-ns",
                metadata=ObjectMetaArgs(
                    name="intel-device-plugins",
                ),
                opts=child_opts,
            )

            # Deploy the Intel GPU Operator using the official Helm chart
            self.gpu_operator = Release(
                "intel-gpu-operator",
                ReleaseArgs(
                    name="intel-gpu-operator",
                    namespace=self.gpu_operator_ns.metadata.name,
                    chart="intel-device-plugins-operator",
                    version="0.35.0",
                    repository_opts=RepositoryOptsArgs(
                        repo="https://intel.github.io/helm-charts/",
                    ),
                    values={
                        "tolerations": [
                            {
                                "key": "gpu.intel.com/i915",
                                "operator": "Exists",
                                "effect": "NoSchedule",
                            }
                        ]
                    },
                ),
                opts=ResourceOptions.merge(
                    child_opts, ResourceOptions(depends_on=self.node_feature_discovery)
                ),
            )

            self.gpu_device = ConfigFile(
                "gpu-device",
                file="./k8s/gpu_operator/intel-gpu-device.yaml",
                opts=ResourceOptions.merge(
                    child_opts, ResourceOptions(depends_on=self.gpu_operator)
                ),
            )
