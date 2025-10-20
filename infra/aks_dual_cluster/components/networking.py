import pulumi
from pulumi import ComponentResource, ResourceOptions
from pulumi_azure_native import network


class NetworkingArgs:
    def __init__(
        self, config: pulumi.config.Config, resource_group_name: str, location: str
    ) -> None:
        self.config = config
        self.resource_group_name = resource_group_name
        self.location = location


class Networking(ComponentResource):
    def __init__(
        self, name: str, args: NetworkingArgs, opts: ResourceOptions | None = None
    ):
        super().__init__("fridge_aks:Networking", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        # Create NSGs for each cluster
        self.private_nsg = network.NetworkSecurityGroup(
            f"{name}-private-nsg",
            resource_group_name=args.resource_group_name,
            location=args.location,
            network_security_group_name=f"{name}-private-nsg",
            security_rules=[
                network.SecurityRuleArgs(
                    name="AllowK8sAPIInBound",
                    priority=100,
                    direction=network.SecurityRuleDirection.INBOUND,
                    access=network.SecurityRuleAccess.ALLOW,
                    protocol=network.SecurityRuleProtocol.ASTERISK,
                    source_port_range="*",
                    destination_port_range="443",
                    source_address_prefix=args.config.require("access_vnet_cidr"),
                    destination_address_prefix="*",
                )
            ],
            opts=child_opts,
        )

        self.access_nsg = network.NetworkSecurityGroup(
            f"{name}-access-nsg",
            resource_group_name=args.resource_group_name,
            location=args.location,
            network_security_group_name=f"{name}-access-nsg",
            security_rules=[
                network.SecurityRuleArgs(
                    name="AllowHTTPSInBound",
                    priority=300,
                    direction=network.SecurityRuleDirection.INBOUND,
                    access=network.SecurityRuleAccess.ALLOW,
                    protocol=network.SecurityRuleProtocol.ASTERISK,
                    source_port_range="*",
                    destination_port_range="443",
                    source_address_prefix="*",
                    destination_address_prefix="*",
                ),
                network.SecurityRuleArgs(
                    name="AllowSSHServerInBound",
                    priority=400,
                    direction=network.SecurityRuleDirection.INBOUND,
                    access=network.SecurityRuleAccess.ALLOW,
                    protocol=network.SecurityRuleProtocol.TCP,
                    source_port_range="*",
                    destination_port_range="2500",
                    source_address_prefix="*",
                    destination_address_prefix="*",
                ),
                network.SecurityRuleArgs(
                    name="DenyAllOtherInbound",
                    priority=500,
                    direction=network.SecurityRuleDirection.INBOUND,
                    access=network.SecurityRuleAccess.DENY,
                    protocol=network.SecurityRuleProtocol.ASTERISK,
                    source_port_range="*",
                    destination_port_range="*",
                    source_address_prefix="*",
                    destination_address_prefix="*",
                ),
            ],
            opts=child_opts,
        )

        # Create VNets and node subnets for each cluster
        self.access_vnet = network.VirtualNetwork(
            f"{name}-access-vnet",
            resource_group_name=args.resource_group_name,
            address_space=network.AddressSpaceArgs(
                address_prefixes=[args.config.require("access_vnet_cidr")]
            ),
            opts=child_opts,
        )

        self.access_nodes = network.Subnet(
            f"{name}-access-nodes",
            resource_group_name=args.resource_group_name,
            virtual_network_name=self.access_vnet.name,
            address_prefix=args.config.require("access_nodes_subnet_cidr"),
            network_security_group=network.NetworkSecurityGroupArgs(
                id=self.access_nsg.id
            ),
            opts=ResourceOptions.merge(
                child_opts, ResourceOptions(depends_on=[self.access_vnet])
            ),
        )

        self.private_vnet = network.VirtualNetwork(
            f"{name}-private-vnet",
            resource_group_name=args.resource_group_name,
            address_space=network.AddressSpaceArgs(
                address_prefixes=[args.config.require("private_vnet_cidr")]
            ),
            opts=child_opts,
        )

        self.private_nodes = network.Subnet(
            f"{name}-private-nodes",
            resource_group_name=args.resource_group_name,
            virtual_network_name=self.private_vnet.name,
            address_prefix=args.config.require("private_nodes_subnet_cidr"),
            network_security_group=network.NetworkSecurityGroupArgs(
                id=self.private_nsg.id
            ),
            opts=ResourceOptions.merge(
                child_opts, ResourceOptions(depends_on=[self.private_vnet])
            ),
        )

        # Set up VNet peering between the two VNets so they can communicate
        self.private_to_access_peering = network.VirtualNetworkPeering(
            f"{name}-private-to-access-peering",
            resource_group_name=args.resource_group_name,
            virtual_network_name=self.private_vnet.name,
            remote_virtual_network=network.SubResourceArgs(id=self.access_vnet.id),
            allow_virtual_network_access=True,
            allow_forwarded_traffic=False,
            allow_gateway_transit=False,
            use_remote_gateways=False,
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(
                    depends_on=[
                        self.private_vnet,
                        self.private_nodes,
                        self.access_vnet,
                        self.access_nodes,
                    ]
                ),
            ),
        )

        self.access_to_private_peering = network.VirtualNetworkPeering(
            f"{name}-access-to-private-peering",
            resource_group_name=args.resource_group_name,
            virtual_network_name=self.access_vnet.name,
            remote_virtual_network=network.SubResourceArgs(id=self.private_vnet.id),
            allow_virtual_network_access=True,
            allow_forwarded_traffic=False,
            allow_gateway_transit=False,
            use_remote_gateways=False,
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(
                    depends_on=[
                        self.private_vnet,
                        self.private_nodes,
                        self.access_vnet,
                        self.access_nodes,
                    ]
                ),
            ),
        )

        self.access_vnet_id = self.access_vnet.id
        self.access_nodes_subnet_id = self.access_nodes.id
        self.private_vnet_id = self.private_vnet.id
        self.private_nodes_subnet_id = self.private_nodes.id

        self.register_outputs(
            {
                "access_vnet": self.access_vnet,
                "private_vnet": self.private_vnet,
                "access_nodes_subnet": self.access_nodes,
                "private_nodes_subnet": self.private_nodes,
                "access_to_private_peering": self.access_to_private_peering,
                "private_to_access_peering": self.private_to_access_peering,
                "access_nsg": self.access_nsg,
                "private_nsg": self.private_nsg,
            }
        )
