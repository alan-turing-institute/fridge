import pulumi
from .stack_outputs import StackOutputs
from pulumi import ComponentResource, ResourceOptions
from pulumi_azure_native import network


class FirewallArgs:
    def __init__(
        self,
        config: pulumi.Config,
        location: str,
        resource_group_name: str,
        stack_outputs: StackOutputs,
    ) -> None:
        self.config = config
        self.location = location
        self.resource_group_name = resource_group_name
        self.stack_outputs = stack_outputs


class Firewall(ComponentResource):
    def __init__(
        self, name: str, args: FirewallArgs, opts: ResourceOptions | None = None
    ) -> None:
        super().__init__("fridge:aks-post-deployment:firewall", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        # Create subnet for firewall
        self.firewall_subnet = network.Subnet(
            "AzureFirewallSubnet",
            resource_group_name=args.resource_group_name,
            subnet_name="AzureFirewallSubnet",
            virtual_network_name=args.stack_outputs.isolated_vnet_name,
            address_prefix="10.20.2.0/24",
            opts=child_opts,
        )
        self.firewall_management_subnet = network.Subnet(
            "AzureFirewallManagementSubnet",
            resource_group_name=args.resource_group_name,
            subnet_name="AzureFirewallManagementSubnet",
            virtual_network_name=args.stack_outputs.isolated_vnet_name,
            address_prefix="10.20.3.0/24",
            opts=child_opts,
        )

        # create public IPs for firewall and firewall management
        self.firewall_public_ip = network.PublicIPAddress(
            f"{name}-firewall-pip",
            resource_group_name=args.resource_group_name,
            location=args.location,
            public_ip_address_name=f"{name}-firewall-pip",
            public_ip_allocation_method=network.IPAllocationMethod.STATIC,
            sku=network.PublicIPAddressSkuArgs(
                name=network.PublicIPAddressSkuName.STANDARD,
            ),
            opts=child_opts,
        )

        self.public_ip_management = network.PublicIPAddress(
            f"{name}-firewall-management-pip",
            resource_group_name=args.resource_group_name,
            location=args.location,
            public_ip_address_name=f"{name}-firewall-management-pip",
            public_ip_allocation_method=network.IPAllocationMethod.STATIC,
            sku=network.PublicIPAddressSkuArgs(
                name=network.PublicIPAddressSkuName.STANDARD,
            ),
            opts=child_opts,
        )

        # Create Azure Firewall
        # A firewall is necessary to support node bootstrapping in the isolated cluster
        # without imposing overly open NSG rules. Node bootstrapping requires
        # outbound connectivity to packages.aks.azure.com, which is not covered by any ServiceTags
        # and does not have a fixed IP address range.

        self.firewall = network.AzureFirewall(
            f"{name}-isolated-firewall",
            resource_group_name=args.resource_group_name,
            location=args.location,
            azure_firewall_name=f"{name}-isolated-firewall",
            ip_configurations=[
                network.AzureFirewallIPConfigurationArgs(
                    name="firewall-ip-config",
                    subnet=network.SubResourceArgs(id=self.firewall_subnet.id),
                    public_ip_address=network.SubResourceArgs(
                        id=self.firewall_public_ip.id
                    ),
                )
            ],
            management_ip_configuration=network.AzureFirewallIPConfigurationArgs(
                name="firewall-management-ip-config",
                subnet=network.SubResourceArgs(id=self.firewall_management_subnet.id),
                public_ip_address=network.SubResourceArgs(
                    id=self.public_ip_management.id
                ),
            ),
            sku=network.AzureFirewallSkuArgs(
                name=network.AzureFirewallSkuName.AZF_W_V_NET,
                tier=network.AzureFirewallSkuTier.BASIC,
            ),
            opts=child_opts,
        )

        self.route_table = network.RouteTable(
            f"{name}-firewall-route-table",
            resource_group_name=args.resource_group_name,
            location=args.location,
            route_table_name=f"{name}-firewall-route-table",
            routes=[
                network.RouteArgs(
                    name="default-route",
                    address_prefix="0.0.0.0/0",
                    next_hop_type=network.RouteNextHopType.VIRTUAL_APPLIANCE,
                    next_hop_ip_address=self.firewall.ip_configurations[
                        0
                    ].private_ip_address,
                )
            ],
            opts=ResourceOptions.merge(
                child_opts, ResourceOptions(parent=self.firewall)
            ),
        )
