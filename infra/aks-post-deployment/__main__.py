import pulumi
import components

config = pulumi.Config()

stack_outputs = components.StackOutputs(
    "stack-outputs",
    args=components.StackOutputsArgs(config=config),
)

dns_zone = components.PrivateDNSZone(
    "private-dns-zone",
    args=components.PrivateDNSZoneArgs(
        resource_group_name=config.require("azure_resource_group"),
        zone_name="aks-dual.fridge.develop.turingsafehaven.ac.uk",
        stack_outputs=stack_outputs,
    ),
)
nsg_rules = components.NetworkSecurityRules(
    "network-security-rules",
    args=components.NetworkSecurityRulesArgs(
        config=config,
        resource_group_name=config.require("azure_resource_group"),
        stack_outputs=stack_outputs,
    ),
)
