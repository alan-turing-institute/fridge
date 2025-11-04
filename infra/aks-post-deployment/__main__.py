import pulumi
from pulumi_azure_native import network

config = pulumi.Config()
organization = config.require("organization_name")
project_name = config.require("project_name")
stack = config.require("infrastructure_stack_name")

test_stack_reference = pulumi.StackReference(f"{organization}/{project_name}/{stack}")

isolated_kubeconfig = test_stack_reference.get_output("isolated_kubeconfig")
access_subnet_nsg = test_stack_reference.get_output("access_subnet_nsg")
isolated_subnet_nsg = test_stack_reference.get_output("isolated_subnet_nsg")


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
                source_address_prefix="10.10.1.0/24",
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
                destination_port_range="8080",
                source_address_prefix="10.20.1.0/24",
                destination_address_prefix="10.10.50.50/32",
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
        ],
        opts=pulumi.ResourceOptions(import_=nsg_info["id"]),
    )


isolated_subnet_nsg_lockdown = isolated_subnet_nsg.apply(create_nsg_lockdown)
