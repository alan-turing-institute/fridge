import pulumi
import components

config = pulumi.Config()

stack_outputs = components.StackOutputs(
    "stack-outputs",
    args=components.StackOutputsArgs(config=config),
)

nsg_rules = components.NetworkSecurityRules(
    "network-security-rules",
    args=components.NetworkSecurityRulesArgs(
        config=config,
        resource_group_name=config.require("azure_resource_group"),
        stack_outputs=stack_outputs,
    ),
)
