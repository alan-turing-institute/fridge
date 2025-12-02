import pulumi
from pulumi import ComponentResource, ResourceOptions
from pulumi_azure_native import network


class PrivateDNSZone(ComponentResource):
    def __init__(
        self,
        name: str,
        resource_group_name: str,
        zone_name: str,
        opts: ResourceOptions | None = None,
    ) -> None:
        super().__init__("fridge:aks-post-deployment:PrivateDNSZone", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        self.dns_zone = network.PrivateZone(
            "private-dns-zone",
            resource_group_name=resource_group_name,
            zone_name=zone_name,
            opts=child_opts,
        )

        self.register_outputs({"dns_zone": self.dns_zone})
