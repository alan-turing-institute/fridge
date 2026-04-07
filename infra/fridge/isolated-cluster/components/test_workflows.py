from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.yaml import ConfigFile

from enums import K8sEnvironment

# Deploys a selection of Argo Workflows templates for benchmarking and testing GPU workloads


class TestWorkflowsArgs:
    def __init__(
        self,
        k8s_environment: K8sEnvironment,
        run_tests: bool,
    ) -> None:
        self.run_tests = run_tests
        self.k8s_environment = k8s_environment


class TestWorkflows(ComponentResource):
    def __init__(
        self, name: str, args: TestWorkflowsArgs, opts: ResourceOptions | None = None
    ) -> None:
        super().__init__("fridge:k8s:TestWorkflows", name, None, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        if args.run_tests:
            if args.k8s_environment == K8sEnvironment.DAWN:
                intel_pvc_attention = ConfigFile(
                    "intel-pvc-attention",
                    file="./k8s/argo_workflows/examples/intel_pvc_attention.yaml",
                    opts=child_opts,
                )

                intel_batched_matmul = ConfigFile(
                    "intel-batched-matmul",
                    file="./k8s/argo_workflows/examples/intel_pvc_batched_matmul.yaml",
                    opts=child_opts,
                )

                intel_cifar10 = ConfigFile(
                    "intel-cifar10",
                    file="./k8s/argo_workflows/examples/intel_pvc_cifar10.yaml",
                    opts=child_opts,
                )

                intel_cifar10_ddp = ConfigFile(
                    "intel-cifar10-ddp",
                    file="./k8s/argo_workflows/examples/intel_pvc_cifar10_ddp.yaml",
                    opts=child_opts,
                )

                intel_conv1d = ConfigFile(
                    "intel-conv1d",
                    file="./k8s/argo_workflows/examples/intel_pvc_conv1d.yaml",
                    opts=child_opts,
                )

                intel_pvc_check = ConfigFile(
                    "intel-pvc-check",
                    file="./k8s/argo_workflows/examples/intel_pvc_check.yaml",
                    opts=child_opts,
                )

                intel_small_cnn = ConfigFile(
                    "intel-small-cnn",
                    file="./k8s/argo_workflows/examples/intel_pvc_simulate.yaml",
                    opts=child_opts,
                )

                intel_simulate_dual = ConfigFile(
                    "intel-simulate-dual",
                    file="./k8s/argo_workflows/examples/intel_pvc_simulate_dual.yaml",
                    opts=child_opts,
                )

                intel_resnet50 = ConfigFile(
                    "intel-resnet50",
                    file="./k8s/argo_workflows/examples/intel_pvc_resnet50.yaml",
                    opts=child_opts,
                )

                intel_resnet50_ddp = ConfigFile(
                    "intel-resnet50-ddp",
                    file="./k8s/argo_workflows/examples/intel_pvc_resnet50_ddp.yaml",
                    opts=child_opts,
                )
