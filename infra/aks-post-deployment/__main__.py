import pulumi
from pulumi_azure_native import network

config = pulumi.Config()

# Import infrastructure stack outputs
organization = config.require("organization_name")
project_name = config.require("project_name")
stack = config.require("infrastructure_stack_name")
infrastructure_stack_reference = pulumi.StackReference(
    f"{organization}/{project_name}/{stack}"
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


def create_nsg_lockdown(nsg_info):
    return network.NetworkSecurityGroup(
        "isolated-subnet-nsg-lockdown",
        resource_group_name=config.require("azure_resource_group"),
        location="uksouth",
        network_security_group_name=nsg_info["name"],
        security_rules=[
            network.SecurityRuleArgs(
                name="AllowFridgeAPIFromAccessInBound",
                priority=100,
                direction=network.SecurityRuleDirection.INBOUND,
                access=network.SecurityRuleAccess.ALLOW,
                protocol=network.SecurityRuleProtocol.TCP,
                source_port_range="*",
                destination_port_range="443",
                source_address_prefix=access_nodes_subnet_cidr,
                destination_address_prefix="*",
                description="Allow FRIDGE API access from access cluster API Proxy",
            ),
            network.SecurityRuleArgs(
                name="DenyAccessVNetInBound",
                priority=2000,
                direction=network.SecurityRuleDirection.INBOUND,
                access=network.SecurityRuleAccess.DENY,
                protocol=network.SecurityRuleProtocol.ASTERISK,
                source_port_range="*",
                destination_port_range="*",
                source_address_prefix="10.10.0.0/16",
                destination_address_prefix="*",
                description="Deny all other traffic from access cluster VNet",
            ),
            # OUTBOUND RULES
            # Deny all other outbound to access cluster
            network.SecurityRuleArgs(
                name="AllowHarborOutBound",
                priority=100,
                direction=network.SecurityRuleDirection.OUTBOUND,
                access=network.SecurityRuleAccess.ALLOW,
                protocol=network.SecurityRuleProtocol.TCP,
                source_port_range="*",
                destination_port_range="8080,80,443",
                source_address_prefix=isolated_nodes_subnet_cidr,
                destination_address_prefix="10.10.1.9/32",
            ),
            network.SecurityRuleArgs(
                name="DenyAccessClusterOutBound",
                priority=4000,
                direction=network.SecurityRuleDirection.OUTBOUND,
                access=network.SecurityRuleAccess.DENY,
                protocol=network.SecurityRuleProtocol.ASTERISK,
                source_port_range="*",
                destination_port_range="*",
                source_address_prefix="*",
                destination_address_prefix="10.10.0.0/16",
                description="Deny all other outbound to access cluster",
            ),
            network.SecurityRuleArgs(
                name="DenyInternetOutBound",
                priority=4100,
                direction=network.SecurityRuleDirection.OUTBOUND,
                access=network.SecurityRuleAccess.DENY,
                protocol=network.SecurityRuleProtocol.ASTERISK,
                source_port_range="*",
                destination_port_range="*",
                source_address_prefix="*",
                destination_address_prefix="Internet",
                description="Deny all outbound to internet",
            ),
        ],
        opts=pulumi.ResourceOptions(import_=nsg_info["id"]),
    )


isolated_subnet_nsg_lockdown = isolated_subnet_nsg.apply(create_nsg_lockdown)
