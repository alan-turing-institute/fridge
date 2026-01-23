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
            f"{organization}/{project_name}/{stack}",
            opts=child_opts,
        )

        # Import access cluster stack outputs
        access_stack = args.config.require("access_cluster_stack_name")
        access_project = "fridge-access"
        self.access_stack = pulumi.StackReference(
            f"{organization}/{access_project}/{access_stack}", opts=child_opts
        )

        # Import isolated cluster stack outputs
        isolated_stack = args.config.require("isolated_cluster_stack_name")
        isolated_project = "fridge-isolated"
        self.isolated_stack = pulumi.StackReference(
            f"{organization}/{isolated_project}/{isolated_stack}",
            opts=child_opts,
        )

        self.access_nodes_subnet_cidr = self.infrastructure_stack.get_output(
            "access_nodes_subnet_cidr"
        )
        self.access_subnet_nsg = self.infrastructure_stack.get_output(
            "access_subnet_nsg"
        )

        self.isolated_subnet_nsg = self.infrastructure_stack.get_output(
            "isolated_subnet_nsg"
        )
        self.isolated_nodes_subnet_cidr = self.infrastructure_stack.get_output(
            "isolated_nodes_subnet_cidr"
        )

        self.harbor_ip_address = self.access_stack.get_output("harbor_ip_address")
