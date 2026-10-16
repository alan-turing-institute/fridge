import pulumi
from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.core.v1 import Namespace
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs
from pulumi_kubernetes.helm.v4 import RepositoryOptsArgs
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs
from pulumi_kubernetes.yaml import ConfigFile

from enums import K8sEnvironment, SoftwareVersion


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
                version=SoftwareVersion.NODE_FEATURE_DISCOVERY.value,
                repository_opts=RepositoryOptsArgs(
                    repo="https://kubernetes-sigs.github.io/node-feature-discovery/charts",
                ),
            ),
            opts=child_opts,
        )

        if args.k8s_environment == K8sEnvironment.DAWN:

            self.gpu_operator_ns = Namespace(
                "gpu-operator-ns",
                metadata=ObjectMetaArgs(
                    name="kube-amd-gpu",
                ),
                opts=child_opts,
            )

            # Deploy the AMD GPU Operator using the official Helm chart
            self.gpu_operator = Release(
                "amd-gpu-operator",
                ReleaseArgs(
                    name="amd-gpu-operator",
                    namespace=self.gpu_operator_ns.metadata.name,
                    chart="gpu-operator-charts",
                    version=SoftwareVersion.AMD_GPU_OPERATOR.value,
                    repository_opts=RepositoryOptsArgs(
                        repo="https://rocm.github.io/gpu-operator",
                    ),
                    values={
                        "node-feature-discovery": {
                            "enabled": False,
                        },
                    },
                ),
                opts=ResourceOptions.merge(
                    child_opts, ResourceOptions(depends_on=self.node_feature_discovery)
                ),
            )
