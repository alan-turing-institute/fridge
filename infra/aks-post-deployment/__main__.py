import pulumi
import components

config = pulumi.Config()

# Import infrastructure stack outputs
organization = config.require("organization_name")
project_name = config.require("project_name")
infrastructure_stack_name = config.require("infrastructure_stack_name")
infrastructure_stack_reference = pulumi.StackReference(
    f"{organization}/{project_name}/{infrastructure_stack_name}"
)

# Import access cluster stack outputs
access_stack_name = config.require("access_cluster_stack_name")
access_project = "fridge-access"
access_stack_reference = pulumi.StackReference(
    f"{organization}/{access_project}/{access_stack_name}"
)

access_nodes_subnet_cidr = infrastructure_stack_reference.get_output(
    "access_nodes_subnet_cidr"
)
access_subnet_nsg = infrastructure_stack_reference.get_output("access_subnet_nsg")
isolated_kubeconfig = infrastructure_stack_reference.get_output("isolated_kubeconfig")
isolated_nodes_subnet_cidr = infrastructure_stack_reference.get_output(
    "isolated_nodes_subnet_cidr"
)
isolated_subnet_nsg = infrastructure_stack_reference.get_output("isolated_subnet_nsg")

nsg_rules = components.NetworkSecurityRules(
    "network-security-rules",
    args=components.NetworkSecurityRulesArgs(
        config=config,
        resource_group_name=config.require("azure_resource_group"),
        access_nodes_subnet_cidr=access_nodes_subnet_cidr,
        isolated_nodes_subnet_cidr=isolated_nodes_subnet_cidr,
        access_subnet_nsg=access_subnet_nsg,
        isolated_subnet_nsg=isolated_subnet_nsg,
    ),
)
