import pulumi
from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.core.v1 import Namespace
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs
from pulumi_kubernetes.helm.v4 import RepositoryOptsArgs
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs

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

        if args.k8s_environment == K8sEnvironment.DAWN:
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
                    namespace=self.gpu_operator_ns.metadata.name,
                    chart="intel-device-plugins-operator",
                    version="0.35.0",
                    repository_opts=RepositoryOptsArgs(
                        repo="https://intel.github.io/helm-charts/",
                    ),
                ),
                opts=child_opts,
            )
