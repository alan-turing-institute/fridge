import pulumi
from pulumi import ComponentResource, ResourceOptions
from pulumi_azure_native import privatedns
from .stack_outputs import StackOutputs


class PrivateDNSZoneArgs:
    def __init__(
        self,
        resource_group_name: str,
        zone_name: str,
        stack_outputs: StackOutputs,
    ) -> None:
        self.resource_group_name = resource_group_name
        self.zone_name = zone_name
        self.stack_outputs = stack_outputs


class PrivateDNSZone(ComponentResource):
    def __init__(
        self,
        name: str,
        args: PrivateDNSZoneArgs,
        opts: ResourceOptions | None = None,
    ) -> None:
        super().__init__("fridge:aks-post-deployment:PrivateDNSZone", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        self.dns_zone = privatedns.PrivateZone(
            "private-dns-zone",
            location="Global",
            resource_group_name=args.resource_group_name,
            private_zone_name=args.zone_name,
            opts=child_opts,
        )

        self.private_records = privatedns.PrivateRecordSet(
            "private-dns-a-record",
            resource_group_name=args.resource_group_name,
            private_zone_name=args.zone_name,
            record_type="A",
            relative_record_set_name="harbor",
            ttl=300,
            a_records=[
                privatedns.ARecordArgs(
                    ipv4_address=args.stack_outputs.harbor_ip_address
                )
            ],
            opts=ResourceOptions.merge(
                ResourceOptions(depends_on=[self.dns_zone]),
                child_opts,
            ),
        )

        self.register_outputs({"dns_zone": self.dns_zone})
