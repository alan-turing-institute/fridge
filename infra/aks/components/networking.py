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

        access_vnet_cidr = args.config.require("access_vnet_cidr")
        access_nodes_cidr = args.config.require("access_nodes_subnet_cidr")

        private_vnet_cidr = args.config.require("private_vnet_cidr")
        private_nodes_cidr = args.config.require("private_nodes_subnet_cidr")

        access_vnet = network.VirtualNetwork(
            f"{name}-access-vnet",
            resource_group_name=args.resource_group_name,
            address_space=network.AddressSpaceArgs(address_prefixes=[access_vnet_cidr]),
            opts=child_opts,
        )

        access_nodes = network.Subnet(
            f"{name}-access-nodes",
            resource_group_name=args.resource_group_name,
            virtual_network_name=access_vnet.name,
            address_prefix=access_nodes_cidr,
            opts=ResourceOptions.merge(
                child_opts, ResourceOptions(depends_on=[access_vnet])
            ),
        )

        private_vnet = network.VirtualNetwork(
            f"{name}-private-vnet",
            resource_group_name=args.resource_group_name,
            address_space=network.AddressSpaceArgs(
                address_prefixes=[private_vnet_cidr]
            ),
            opts=child_opts,
        )

        private_nodes = network.Subnet(
            f"{name}-private-nodes",
            resource_group_name=args.resource_group_name,
            virtual_network_name=private_vnet.name,
            address_prefix=private_nodes_cidr,
            opts=ResourceOptions.merge(
                child_opts, ResourceOptions(depends_on=[private_vnet])
            ),
        )

        self.access_nodes_subnet_id = access_nodes.id
        self.private_nodes_subnet_id = private_nodes.id

        self.register_outputs(
            {
                "access_vnet": access_vnet,
                "private_vnet": private_vnet,
            }
        )
