import pulumi
from pulumi import ComponentResource, ResourceOptions
from enums import FridgeStack


class StackOutputsArgs:
    def __init__(self, config: pulumi.config.Config) -> None:
        self.config = config


class StackOutputs(ComponentResource):
    def __init__(
        self, name: str, args: StackOutputsArgs, opts: ResourceOptions | None = None
    ) -> None:
        super().__init__("fridge:aks-post-deployment:StackOutputs", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        # Import infrastructure stack outputs
        organization = args.config.require("organization_name")
        project_name = args.config.require("project_name")
        stack = args.config.require("infrastructure_stack_name")
        self.infrastructure_stack = pulumi.StackReference(
            f"{organization}/{project_name}/{stack}"
        )

        # Import access cluster stack outputs
        access_stack = args.config.require("access_cluster_stack_name")
        access_project = "fridge-access"
        self.access_stack = pulumi.StackReference(
            f"{organization}/{access_project}/{access_stack}"
        )

        # Import isolated cluster stack outputs
        isolated_stack = args.config.require("isolated_cluster_stack_name")
        isolated_project = "fridge-isolated"
        self.isolated_stack = pulumi.StackReference(
            f"{organization}/{isolated_project}/{isolated_stack}"
        )

        def get_vnet_nsg(stack_name: FridgeStack) -> pulumi.Output[str]:
            match stack_name:
                case FridgeStack.ACCESS:
                    return self.infrastructure_stack.get_output("access_subnet_nsg")
                case FridgeStack.ISOLATED:
                    return self.infrastructure_stack.get_output("isolated_subnet_nsg")
                case _:
                    raise ValueError(f"Unsupported stack name: {stack_name}")

        def get_node_subnet_cidr(stack_name: FridgeStack) -> pulumi.Output[str]:
            match stack_name:
                case FridgeStack.ACCESS:
                    return self.infrastructure_stack.get_output(
                        "access_nodes_subnet_cidr"
                    )
                case FridgeStack.ISOLATED:
                    return self.infrastructure_stack.get_output(
                        "isolated_nodes_subnet_cidr"
                    )
                case _:
                    raise ValueError(f"Unsupported stack name: {stack_name}")
