import pulumi
from .stack_outputs import StackOutputs
from pulumi import ComponentResource, ResourceOptions
from pulumi_azure_native import network


class NetworkSecurityRulesArgs:
    def __init__(
        self,
        config: pulumi.config.Config,
        resource_group_name: str,
        stack_outputs: StackOutputs,
    ):
        self.config = config
        self.resource_group_name = resource_group_name
        self.stack_outputs = stack_outputs


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

        access_nodes_subnet_cidr = args.stack_outputs.access_nodes_subnet_cidr
        isolated_nodes_subnet_cidr = args.stack_outputs.isolated_nodes_subnet_cidr
        isolated_cluster_k8s_api_ip = args.stack_outputs.isolated_cluster_api_server_ip
        fridge_api_ip = args.stack_outputs.fridge_api_ip

        access_cluster_nsg_rules = [
            network.SecurityRuleArgs(
                name="AllowHTTPSInbound",
                priority=100,
                direction=network.SecurityRuleDirection.INBOUND,
                access=network.SecurityRuleAccess.ALLOW,
                protocol=network.SecurityRuleProtocol.ASTERISK,
                source_port_range="*",
                destination_port_range="443",
                source_address_prefix="Internet",
                destination_address_prefix="*",
                description="Allow HTTPS traffic for Harbor",
            ),
            network.SecurityRuleArgs(
                name="AllowSSHServerInbound",
                priority=200,
                direction=network.SecurityRuleDirection.INBOUND,
                access=network.SecurityRuleAccess.ALLOW,
                protocol=network.SecurityRuleProtocol.TCP,
                source_port_range="*",
                destination_port_range="2500",
                source_address_prefix="Internet",
                destination_address_prefix="*",
                description="Allow SSH traffic to API Proxy SSH server",
            ),
            # Allow Azure Load Balancer health probes
            network.SecurityRuleArgs(
                name="AllowAzureLoadBalancerInbound",
                priority=400,
                direction=network.SecurityRuleDirection.INBOUND,
                access=network.SecurityRuleAccess.ALLOW,
                protocol=network.SecurityRuleProtocol.ASTERISK,
                source_port_range="*",
                destination_port_range="*",
                source_address_prefix="AzureLoadBalancer",
                destination_address_prefix="*",
                description="Allow Azure Load Balancer health probes",
            ),
            # Allow Harbor requests from isolated cluster
            network.SecurityRuleArgs(
                name="AllowHarborFromIsolatedInBound",
                priority=500,
                direction=network.SecurityRuleDirection.INBOUND,
                access=network.SecurityRuleAccess.ALLOW,
                protocol=network.SecurityRuleProtocol.TCP,
                source_port_range="*",
                destination_port_range="80",
                source_address_prefix=isolated_nodes_subnet_cidr,
                destination_address_prefix=args.stack_outputs.harbor_ip_address,
                description="Allow Harbor access from Isolated cluster",
            ),
            network.SecurityRuleArgs(
                name="DenyIsolatedClusterInBound",
                priority=1000,
                direction=network.SecurityRuleDirection.INBOUND,
                access=network.SecurityRuleAccess.DENY,
                protocol=network.SecurityRuleProtocol.ASTERISK,
                source_port_range="*",
                destination_port_range="*",
                source_address_prefix=isolated_nodes_subnet_cidr,
                destination_address_prefix="*",
                description="Deny all other inbound from Isolated cluster",
            ),
            # Outbound rules
            # Note: this allows access to any node in the Isolated cluster on port 443
            # The specific IP addresses of the API server and FRIDGE API are not known in advance
            # so we allow access to the whole subnet. In practice, only the API Proxy pod
            # will be making these requests. This can potentially be tightened after FRIDGE deployment.
            network.SecurityRuleArgs(
                name="AllowAPIProxyToIsolatedOutBound",
                priority=100,
                direction=network.SecurityRuleDirection.OUTBOUND,
                access=network.SecurityRuleAccess.ALLOW,
                protocol=network.SecurityRuleProtocol.TCP,
                source_port_range="*",
                destination_port_ranges=[
                    "443",
                ],
                source_address_prefix="*",
                destination_address_prefix=isolated_cluster_k8s_api_ip,  # isolated_nodes_subnet_cidr,
                description="Allow API Proxy to access k8s API and FRIDGE API in Isolated cluster",
            ),
            network.SecurityRuleArgs(
                name="AllowFridgeAPIOutBound",
                priority=200,
                direction=network.SecurityRuleDirection.OUTBOUND,
                access=network.SecurityRuleAccess.ALLOW,
                protocol=network.SecurityRuleProtocol.TCP,
                source_port_range="*",
                destination_port_range="443",
                source_address_prefix="*",
                destination_address_prefix=fridge_api_ip,
                description="Allow access to FRIDGE API in Isolated cluster",
            ),
            # Deny all other outbound to Isolated cluster (except allowed APIs)
            network.SecurityRuleArgs(
                name="DenyIsolatedClusterOutBound",
                priority=4000,
                direction=network.SecurityRuleDirection.OUTBOUND,
                access=network.SecurityRuleAccess.DENY,
                protocol=network.SecurityRuleProtocol.ASTERISK,
                source_port_range="*",
                destination_port_range="*",
                source_address_prefix="*",
                destination_address_prefix=isolated_nodes_subnet_cidr,
                description="Deny all other outbound to Isolated cluster",
            ),
        ]

        isolated_cluster_nsg_rules = [
            network.SecurityRuleArgs(
                name="AllowFridgeAPIFromAccessInBound",
                priority=100,
                direction=network.SecurityRuleDirection.INBOUND,
                access=network.SecurityRuleAccess.ALLOW,
                protocol=network.SecurityRuleProtocol.TCP,
                source_port_range="*",
                destination_port_range="443",
                source_address_prefix=access_nodes_subnet_cidr,
                destination_address_prefix=fridge_api_ip,
                description="Allow FRIDGE API access from access cluster API Proxy",
            ),
            network.SecurityRuleArgs(
                name="AllowK8sAPIFromAccessInBound",
                priority=200,
                direction=network.SecurityRuleDirection.INBOUND,
                access=network.SecurityRuleAccess.ALLOW,
                protocol=network.SecurityRuleProtocol.TCP,
                source_port_range="*",
                destination_port_range="443",
                source_address_prefix=access_nodes_subnet_cidr,
                destination_address_prefix=isolated_cluster_k8s_api_ip,
                description="Allow k8s API access from access cluster API Proxy",
            ),
            network.SecurityRuleArgs(
                name="DenyAccessVNetInBound",
                priority=2000,
                direction=network.SecurityRuleDirection.INBOUND,
                access=network.SecurityRuleAccess.DENY,
                protocol=network.SecurityRuleProtocol.ASTERISK,
                source_port_range="*",
                destination_port_range="*",
                source_address_prefix=args.stack_outputs.access_nodes_subnet_cidr,
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
                destination_port_range="80",
                source_address_prefix=isolated_nodes_subnet_cidr,
                destination_address_prefix=args.stack_outputs.harbor_ip_address,
            ),
            network.SecurityRuleArgs(
                name="AllowAccessToStorageOutbound",
                priority=200,
                direction=network.SecurityRuleDirection.OUTBOUND,
                access=network.SecurityRuleAccess.ALLOW,
                protocol=network.SecurityRuleProtocol.TCP,
                source_address_prefix=isolated_nodes_subnet_cidr,
                destination_address_prefix="Storage",
                source_port_range="*",
                destination_port_range="445",
            ),
            network.SecurityRuleArgs(
                name="DenyAccessClusterOutBound",
                priority=3900,
                direction=network.SecurityRuleDirection.OUTBOUND,
                access=network.SecurityRuleAccess.DENY,
                protocol=network.SecurityRuleProtocol.ASTERISK,
                source_port_range="*",
                destination_port_range="*",
                source_address_prefix="*",
                destination_address_prefix=access_nodes_subnet_cidr,
                description="Deny all other outbound to access cluster",
            ),
            network.SecurityRuleArgs(
                name="DenyInternetOutBound",
                priority=4000,
                direction=network.SecurityRuleDirection.OUTBOUND,
                access=network.SecurityRuleAccess.DENY,
                protocol=network.SecurityRuleProtocol.ASTERISK,
                source_port_range="*",
                destination_port_range="*",
                source_address_prefix="*",
                destination_address_prefix="Internet",
                description="Deny all outbound to internet",
            ),
        ]

        # Create access NSG lockdown rules
        def lockdown_access_nsg(nsg_info):
            return network.NetworkSecurityGroup(
                "access-subnet-nsg-lockdown",
                resource_group_name=args.config.require("azure_resource_group"),
                location="uksouth",
                network_security_group_name=nsg_info["name"],
                security_rules=access_cluster_nsg_rules,
                opts=ResourceOptions.merge(
                    ResourceOptions(import_=nsg_info["id"]),
                    child_opts,
                ),
            )

        def lockdown_isolated_nsg(nsg_info):
            return network.NetworkSecurityGroup(
                "isolated-subnet-nsg-lockdown",
                resource_group_name=args.config.require("azure_resource_group"),
                location="uksouth",
                network_security_group_name=nsg_info["name"],
                security_rules=isolated_cluster_nsg_rules,
                opts=ResourceOptions.merge(
                    ResourceOptions(import_=nsg_info["id"]),
                    child_opts,
                ),
            )

        self.access_subnet_nsg_lockdown = args.stack_outputs.access_subnet_nsg.apply(
            lockdown_access_nsg
        )

        self.isolated_subnet_nsg_lockdown = (
            args.stack_outputs.isolated_subnet_nsg.apply(lockdown_isolated_nsg)
        )
