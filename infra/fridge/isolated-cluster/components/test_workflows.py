import pulumi
from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.yaml import ConfigFile


class TestWorkflowsArgs:
    def __init__(
        self,
        run_tests: bool,
    ) -> None:
        self.run_tests = run_tests


class TestWorkflows(ComponentResource):
    def __init__(
        self, name: str, args: TestWorkflowsArgs, opts: ResourceOptions | None = None
    ) -> None:
        super().__init__("fridge:k8s:TestWorkflows", name, None, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        if args.run_tests:
            intel_pvc_check = ConfigFile(
                "intel-pvc-check",
                file="./k8s/argo_workflows/examples/intel_pvc_check.yaml",
                opts=child_opts,
            )
