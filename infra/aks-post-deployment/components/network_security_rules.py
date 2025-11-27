import pulumi
from pulumi import ComponentResource, ResourceOptions
from pulumi_azure_native import network


class NetworkSecurityRulesArgs:
    def __init__(
        self,
        config: pulumi.config.Config,
        resource_group_name: str,
        access_nodes_subnet_cidr: pulumi.Output[str],
        isolated_nodes_subnet_cidr: pulumi.Output[str],
        access_subnet_nsg: pulumi.Output[str],
        isolated_subnet_nsg: pulumi.Output[str],
    ):
        self.config = config
        self.resource_group_name = resource_group_name
        self.access_nodes_subnet_cidr = access_nodes_subnet_cidr
        self.isolated_nodes_subnet_cidr = isolated_nodes_subnet_cidr
        self.access_subnet_nsg = access_subnet_nsg
        self.isolated_subnet_nsg = isolated_subnet_nsg


class NetworkSecurityRules(ComponentResource):
    def __init__(
        self,
        name: str,
        args: NetworkSecurityRulesArgs,
        opts: ResourceOptions | None = None,
    ) -> None:
        super().__init__(
            "fridge:aks-post-deployment:NetworkSecurityRules", name, {}, opts
        )
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        self.access_subnet_nsg_lockdown = network.NetworkSecurityGroup(
            "access-subnet-nsg-lockdown",
            resource_group_name=args.resource_group_name,
            location="uksouth",
            network_security_group_name=args.access_subnet_nsg,
            security_rules=[
                network.SecurityRuleArgs(
                    name="DenyIsolatedVNetInBound",
                    priority=2000,
                    direction=network.SecurityRuleDirection.INBOUND,
                    access=network.SecurityRuleAccess.DENY,
                    protocol=network.SecurityRuleProtocol.ASTERISK,
                    source_port_range="*",
                    destination_port_range="*",
                    source_address_prefix=args.isolated_nodes_subnet_cidr,
                    destination_address_prefix="*",
                    description="Deny access from isolated cluster VNet",
                ),
            ],
            opts=child_opts,
        )

        def create_nsg_lockdown(nsg_info):
            return network.NetworkSecurityGroup(
                "isolated-subnet-nsg-lockdown",
                resource_group_name=args.config.require("azure_resource_group"),
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
                        source_address_prefix=args.access_nodes_subnet_cidr,
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
                        source_address_prefix=args.isolated_nodes_subnet_cidr,
                        destination_address_prefix=args.access_stack_reference.get_output(
                            "harbor_ip_address"
                        ),
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

        self.isolated_subnet_nsg_lockdown = args.isolated_subnet_nsg.apply(
            create_nsg_lockdown
        )
