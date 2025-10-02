import pulumi
import pulumi_tls as tls

from pulumi import ComponentResource, ResourceOptions
from pulumi_azure_native import (
    compute,
    managedidentity,
)
from pulumi_azure_native.containerservice import (
    AdvancedNetworkingArgs,
    AdvancedNetworkingObservabilityArgs,
    ContainerServiceLinuxProfileArgs,
    ContainerServiceSshConfigurationArgs,
    ContainerServiceSshPublicKeyArgs,
    ContainerServiceNetworkProfileArgs,
    ManagedCluster,
    ManagedClusterAgentPoolProfileArgs,
    ManagedClusterAPIServerAccessProfileArgs,
    ManagedClusterIdentityArgs,
    NetworkDataplane,
    NetworkPlugin,
    NetworkPluginMode,
    NetworkPolicy,
    ResourceIdentityType,
)


class PrivateClusterArgs:
    def __init__(
        self,
        cluster_name: str,
        config: pulumi.config.Config,
        disk_encryption_set: compute.DiskEncryptionSet,
        identity: managedidentity.UserAssignedIdentity,
        nodes_subnet_id: str,
        resource_group_name: str,
        ssh_key: tls.PrivateKey,
    ) -> None:
        self.cluster_name = cluster_name
        self.config = config
        self.disk_encryption_set = disk_encryption_set
        self.identity = identity
        self.nodes_subnet_id = nodes_subnet_id
        self.resource_group_name = resource_group_name
        self.ssh_key = ssh_key


class PrivateCluster(ComponentResource):
    def __init__(
        self, name: str, args: PrivateClusterArgs, opts: ResourceOptions = None
    ):
        super().__init__("fridge_aks:PrivateCluster", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        self.private_cluster = ManagedCluster(
            args.cluster_name,
            resource_group_name=args.resource_group_name,
            api_server_access_profile=ManagedClusterAPIServerAccessProfileArgs(
                enable_private_cluster=True,
            ),
            agent_pool_profiles=[
                ManagedClusterAgentPoolProfileArgs(
                    enable_auto_scaling=True,
                    max_count=5,
                    max_pods=100,
                    min_count=2,
                    mode="System",
                    name="gppool",
                    node_labels={
                        "context": "fridge",
                        "size": "B4als_v2",
                        "arch": "x86_64",
                    },
                    os_disk_size_gb=0,  # when == 0 sets default size
                    os_type="Linux",
                    os_sku="Ubuntu",
                    type="VirtualMachineScaleSets",
                    vm_size="Standard_B4als_v2",
                    vnet_subnet_id=args.nodes_subnet_id,
                ),
                ManagedClusterAgentPoolProfileArgs(
                    enable_auto_scaling=True,
                    max_count=5,
                    max_pods=100,
                    min_count=2,
                    mode="System",
                    name="systempool",
                    node_labels={
                        "context": "fridge",
                        "size": "B2als_v2",
                        "arch": "x86_64",
                    },
                    node_taints=[
                        # allow only system pods
                        # https://learn.microsoft.com/en-us/azure/aks/use-system-pools?tabs=azure-cli#system-and-user-node-pools
                        "CriticalAddonsOnly=true:NoSchedule",
                    ],
                    os_disk_size_gb=0,  # when == 0 sets default size
                    os_type="Linux",
                    os_sku="Ubuntu",
                    type="VirtualMachineScaleSets",
                    vm_size="Standard_B2als_v2",
                    vnet_subnet_id=args.nodes_subnet_id,
                ),
            ],
            # disk_encryption_set_id=args.disk_encryption_set.id,
            dns_prefix="fridge-private",
            identity=ManagedClusterIdentityArgs(
                type=ResourceIdentityType.USER_ASSIGNED,
                user_assigned_identities=[args.identity.id],
            ),
            kubernetes_version="1.33",
            linux_profile=ContainerServiceLinuxProfileArgs(
                admin_username="fridgeadmin",
                ssh=ContainerServiceSshConfigurationArgs(
                    public_keys=[
                        ContainerServiceSshPublicKeyArgs(
                            key_data=args.ssh_key.public_key_openssh,
                        )
                    ],
                ),
            ),
            network_profile=ContainerServiceNetworkProfileArgs(
                advanced_networking=AdvancedNetworkingArgs(
                    enabled=True,
                    observability=AdvancedNetworkingObservabilityArgs(
                        enabled=True,
                    ),
                ),
                network_dataplane=NetworkDataplane.CILIUM,
                network_plugin=NetworkPlugin.AZURE,
                network_plugin_mode=NetworkPluginMode.OVERLAY,
                network_policy=NetworkPolicy.CILIUM,
            ),
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(replace_on_changes=["agent_pool_profiles"]),
            ),
        )

        self.name = self.private_cluster.name
        self.private_fqdn = self.private_cluster.private_fqdn
        self.register_outputs({"private_cluster": self.private_cluster})
