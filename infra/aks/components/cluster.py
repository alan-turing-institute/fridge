import pulumi

from pulumi import ComponentResource, ResourceOptions
from pulumi_azure_native import (
    authorization,
    compute,
    containerservice,
    keyvault,
    managedidentity,
    resources,
)


class ClusterArgs:
    def __init__(
        self,
        config: pulumi.config.Config,
        resource_group_name: str,
        cluster_name: str,
        use_private_cluster: bool = False,
    ) -> None:
        self.config = config
        self.resource_group_name = resource_group_name
        self.cluster_name = cluster_name
        self.use_private_cluster = use_private_cluster


class Cluster(ComponentResource):
    def __init__(self, name: str, args: ClusterArgs, opts: ResourceOptions = None):
        super().__init__("fridge_aks:Cluster", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        access_cluster = containerservice.ManagedCluster(
            f"{args.config.require('cluster_name')}-access",
            resource_group_name=args.resource_group.name,
            agent_pool_profiles=[
                containerservice.ManagedClusterAgentPoolProfileArgs(
                    enable_auto_scaling=True,
                    max_count=5,
                    max_pods=100,
                    min_count=3,
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
                ),
                containerservice.ManagedClusterAgentPoolProfileArgs(
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
                ),
            ],
            disk_encryption_set_id=disk_encryption_set.id,
            dns_prefix="fridge",
            identity=containerservice.ManagedClusterIdentityArgs(
                type=containerservice.ResourceIdentityType.USER_ASSIGNED,
                user_assigned_identities=[identity.id],
            ),
            kubernetes_version="1.32",
            linux_profile=containerservice.ContainerServiceLinuxProfileArgs(
                admin_username="fridgeadmin",
                ssh=containerservice.ContainerServiceSshConfigurationArgs(
                    public_keys=[
                        containerservice.ContainerServiceSshPublicKeyArgs(
                            key_data=ssh_key.public_key_openssh,
                        )
                    ],
                ),
            ),
            network_profile=containerservice.ContainerServiceNetworkProfileArgs(
                advanced_networking=containerservice.AdvancedNetworkingArgs(
                    enabled=True,
                    observability=containerservice.AdvancedNetworkingObservabilityArgs(
                        enabled=True,
                    ),
                ),
                network_dataplane=containerservice.NetworkDataplane.CILIUM,
                network_plugin=containerservice.NetworkPlugin.AZURE,
                network_policy=containerservice.NetworkPolicy.CILIUM,
            ),
            opts=pulumi.ResourceOptions(replace_on_changes=["agent_pool_profiles"]),
        )

        self.register_outputs({"access_cluster": access_cluster})
