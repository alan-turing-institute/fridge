from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.yaml.v2 import ConfigGroup

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
            match args.k8s_environment:
                case K8sEnvironment.DAWN:
                    intel_examples = ConfigGroup(
                        "intel-examples",
                        files=[
                            "./k8s/argo_workflows/examples/intel_gpu_attention.yaml",
                            "./k8s/argo_workflows/examples/intel_gpu_batched_matmul.yaml",
                            "./k8s/argo_workflows/examples/intel_gpu_cifar10.yaml",
                            "./k8s/argo_workflows/examples/intel_gpu_check.yaml",
                        ],
                        opts=child_opts,
                    )
                    self.register_outputs(
                        {
                            "intel_examples": intel_examples,
                        }
                    )
                case K8sEnvironment.ZENITH:
                    amd_examples = ConfigGroup(
                        "amd-examples",
                        files=[
                            "./k8s/argo_workflows/examples/amd_mi355x_attention.yaml",
                            "./k8s/argo_workflows/examples/amd_mi355x_batched_matmul.yaml",
                            "./k8s/argo_workflows/examples/amd_mi355x_cifar10.yaml",
                            "./k8s/argo_workflows/examples/amd_mi355x_check.yaml",
                            "./k8s/argo_workflows/examples/amd_mi355x_conv1d.yaml",
                            "./k8s/argo_workflows/examples/amd_mi355x_simulate.yaml",
                            "./k8s/argo_workflows/examples/amd_mi355x_resnet50.yaml",
                        ],
                        opts=child_opts,
                    )
                    self.register_outputs(
                        {
                            "amd_examples": amd_examples,
                        }
                    )
