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
    def __init__(self, name: str, args: NetworkingArgs, opts: ResourceOptions = None):
        super().__init__("fridge_aks:Networking", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        # Create NSGs

        private_nsg = network.NetworkSecurityGroup(
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
                    destination_port_range="6443",
                    source_address_prefix="10.10.0.0/16",  # Access cluster VNet
                    destination_address_prefix="*",
                )
            ],
            opts=child_opts,
        )

        access_nsg = network.NetworkSecurityGroup(
            f"{name}-access-nsg",
            resource_group_name=args.resource_group_name,
            location=args.location,
            network_security_group_name=f"{name}-access-nsg",
            security_rules=[
                network.SecurityRuleArgs(
                    name="AllowK8sAPIInBound",
                    priority=100,
                    direction=network.SecurityRuleDirection.INBOUND,
                    access=network.SecurityRuleAccess.ALLOW,
                    protocol=network.SecurityRuleProtocol.ASTERISK,
                    source_port_range="*",
                    destination_port_range="6443",
                    source_address_prefix="*",
                    destination_address_prefix="*",
                ),
                network.SecurityRuleArgs(
                    name="AllowHTTPInBound",
                    priority=200,
                    direction=network.SecurityRuleDirection.INBOUND,
                    access=network.SecurityRuleAccess.ALLOW,
                    protocol=network.SecurityRuleProtocol.ASTERISK,
                    source_port_range="*",
                    destination_port_range="80",
                    source_address_prefix="*",
                    destination_address_prefix="*",
                ),
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
            ],
            opts=child_opts,
        )

        # Create VNets and node subnets for each cluster
        access_vnet = network.VirtualNetwork(
            f"{name}-access-vnet",
            resource_group_name=args.resource_group_name,
            address_space=network.AddressSpaceArgs(address_prefixes=["10.10.0.0/16"]),
            opts=child_opts,
        )

        access_nodes = network.Subnet(
            f"{name}-access-nodes",
            resource_group_name=args.resource_group_name,
            virtual_network_name=access_vnet.name,
            address_prefix="10.10.1.0/24",
            network_security_group=network.NetworkSecurityGroupArgs(id=access_nsg.id),
            opts=ResourceOptions.merge(
                child_opts, ResourceOptions(depends_on=[access_vnet])
            ),
        )

        private_vnet = network.VirtualNetwork(
            f"{name}-private-vnet",
            resource_group_name=args.resource_group_name,
            address_space=network.AddressSpaceArgs(address_prefixes=["10.20.0.0/16"]),
            opts=child_opts,
        )

        private_nodes = network.Subnet(
            f"{name}-private-nodes",
            resource_group_name=args.resource_group_name,
            virtual_network_name=private_vnet.name,
            address_prefix="10.20.1.0/24",
            network_security_group=network.NetworkSecurityGroupArgs(id=private_nsg.id),
            opts=ResourceOptions.merge(
                child_opts, ResourceOptions(depends_on=[private_vnet])
            ),
        )

        # Set up VNet peering between the two VNets so they can communicate
        private_to_access_peering = network.VirtualNetworkPeering(
            f"{name}-private-to-access-peering",
            resource_group_name=args.resource_group_name,
            virtual_network_name=private_vnet.name,
            remote_virtual_network=network.SubResourceArgs(id=access_vnet.id),
            allow_virtual_network_access=True,
            allow_forwarded_traffic=True,
            allow_gateway_transit=False,
            use_remote_gateways=False,
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(
                    depends_on=[private_vnet, private_nodes, access_vnet, access_nodes]
                ),
            ),
        )

        access_to_private_peering = network.VirtualNetworkPeering(
            f"{name}-access-to-private-peering",
            resource_group_name=args.resource_group_name,
            virtual_network_name=access_vnet.name,
            remote_virtual_network=network.SubResourceArgs(id=private_vnet.id),
            allow_virtual_network_access=True,
            allow_forwarded_traffic=True,
            allow_gateway_transit=False,
            use_remote_gateways=False,
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(
                    depends_on=[private_vnet, private_nodes, access_vnet, access_nodes]
                ),
            ),
        )

        self.access_vnet_id = access_vnet.id
        self.access_nodes_subnet_id = access_nodes.id
        self.private_vnet_id = private_vnet.id
        self.private_nodes_subnet_id = private_nodes.id

        self.register_outputs(
            {
                "access_vnet": access_vnet,
                "private_vnet": private_vnet,
                "access_nodes_subnet": access_nodes,
                "private_nodes_subnet": private_nodes,
                "access_to_private_peering": access_to_private_peering,
                "private_to_access_peering": private_to_access_peering,
            }
        )
