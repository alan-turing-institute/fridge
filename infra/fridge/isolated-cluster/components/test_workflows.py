from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.yaml import ConfigFile

from enums import K8sEnvironment


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
                intel_pvc_check = ConfigFile(
                    "intel-pvc-check",
                    file="./k8s/argo_workflows/examples/intel_pvc_check.yaml",
                    opts=child_opts,
                )
