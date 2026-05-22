import pulumi
from pulumi import ComponentResource, ResourceOptions
from pulumi_azure_native import network


class FirewallArgs:
    def __init__(
        self,
        config: pulumi.Config,
        location: str,
        resource_group_name: str,
    ) -> None:
        self.config = config
        self.location = location
        self.resource_group_name = resource_group_name


class Firewall(ComponentResource):
    def __init__(
        self, name: str, args: FirewallArgs, opts: ResourceOptions | None = None
    ) -> None:
        super().__init__("fridge:aks-post-deployment:firewall", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        # Create Azure Firewall
        # A firewall is necessary to support node bootstrapping in the isolated cluster
        # without imposing overly open NSG rules. Node bootstrapping requires
        # outbound connectivity to packages.aks.azure.com, which is not covered by any ServiceTags
        # and does not have a fixed IP address range.

        self.firewall_public_ip = network.PublicIPAddress(
            "fridge-firewall-pip",
            resource_group_name=args.resource_group_name,
            location=args.location,
            public_ip_allocation_method=network.IPAllocationMethod.DYNAMIC,
            sku=network.PublicIPAddressSkuArgs(
                name=network.PublicIPAddressSkuName.STANDARD,
            ),
            opts=child_opts,
        )

        self.firewall = network.AzureFirewall(
            "fridge-firewall",
            resource_group_name=args.resource_group_name,
            location=args.location,
            opts=child_opts,
        )
