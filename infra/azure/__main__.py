"""An Azure RM Python Pulumi program"""

import pulumi
from pulumi_azure_native import containerservice, resources
import pulumi_tls as tls

config = pulumi.Config()

resource_group = resources.ResourceGroup(config.require("resource_group_name"))

ssh_key = tls.PrivateKey("ssh-key", algorithm="RSA", rsa_bits="3072")

managed_cluster = containerservice.ManagedCluster(
    "cluster",
    resource_group_name=resource_group.name,
    agent_pool_profiles=[
        containerservice.ManagedClusterAgentPoolProfileArgs(
            count=2,
            max_pods=100,
            mode="System",
            name="gppool",
            node_labels={
                "context": "fridge",
                "size": "D2s_v6",
                "arch": "x86_64",
            },
            os_disk_size_gb=0,  # when == 0 sets default size
            os_type="Linux",
            os_sku="Ubuntu",
            type="VirtualMachineScaleSets",
            vm_size="Standard_D2s_v6",
        ),
    ],
    dns_prefix="fridge",
    identity=containerservice.ManagedClusterIdentityArgs(
        type=containerservice.ResourceIdentityType.SYSTEM_ASSIGNED,
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
)
