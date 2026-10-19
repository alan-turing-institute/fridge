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

        if args.run_tests and args.k8s_environment == K8sEnvironment.DAWN:
            amd_pvc_attention = ConfigFile(
                "amd-pvc-attention",
                file="./k8s/argo_workflows/examples/amd_mi355x_attention.yaml",
                opts=child_opts,
            )

            amd_batched_matmul = ConfigFile(
                "amd-batched-matmul",
                file="./k8s/argo_workflows/examples/amd_mi355x_batched_matmul.yaml",
                opts=child_opts,
            )

            amd_cifar10 = ConfigFile(
                "amd-cifar10",
                file="./k8s/argo_workflows/examples/amd_mi355x_cifar10.yaml",
                opts=child_opts,
            )

            amd_check = ConfigFile(
                "amd-check",
                file="./k8s/argo_workflows/examples/amd_mi355x_check.yaml",
                opts=child_opts,
            )

            amd_conv1d = ConfigFile(
                "amd-conv1d",
                file="./k8s/argo_workflows/examples/amd_mi355x_conv1d.yaml",
                opts=child_opts,
            )

            amd_small_cnn = ConfigFile(
                "amd-small-cnn",
                file="./k8s/argo_workflows/examples/amd_mi355x_simulate.yaml",
                opts=child_opts,
            )

            amd_resnet50 = ConfigFile(
                "amd-resnet50",
                file="./k8s/argo_workflows/examples/amd_mi355x_resnet50.yaml",
                opts=child_opts,
            )

            # to test DDP, we deploy a service so that the ranks can rendezvous and communicate with each other
            amd_ddp_service = ConfigFile(
                "amd-ddp-service",
                file="./k8s/argo_workflows/examples/amd_mi355x_ddp_service.yaml",
                opts=child_opts,
            )

            amd_resnet50_ddp = ConfigFile(
                "amd-resnet50-ddp",
                file="./k8s/argo_workflows/examples/amd_mi355x_resnet50_ddp.yaml",
                opts=ResourceOptions.merge(
                    child_opts,
                    ResourceOptions(depends_on=[amd_ddp_service]),
                ),
            )
