"""An Azure RM Python Pulumi program"""

import base64

import pulumi
from pulumi_azure_native import (
    containerservice, managedidentity, resources
)
import pulumi_tls as tls

import pulumi_kubernetes as k8s

def get_kubeconfig(
    credentials: list[containerservice.outputs.CredentialResultResponse]
) -> str:
    for credential in credentials:
        if credential.name == "clusterAdmin":
            return base64.b64decode(credential.value).decode()


config = pulumi.Config()

resource_group = resources.ResourceGroup(
    "resource_group",
    resource_group_name=config.require("resource_group_name"),
)

ssh_key = tls.PrivateKey("ssh-key", algorithm="RSA", rsa_bits="3072")

identity = managedidentity.UserAssignedIdentity(
    "cluster_managed_identity", resource_group_name=resource_group.name,
)

managed_cluster = containerservice.ManagedCluster(
    "cluster",
    resource_group_name=resource_group.name,
    agent_pool_profiles=[
        containerservice.ManagedClusterAgentPoolProfileArgs(
            count=3,
            max_pods=100,
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
            count=2,
            max_pods=100,
            mode="System",
            name="systempool",
            node_labels={
                "context": "fridge",
                "size": "B2als_v2",
                "arch": "x86_64",
            },
            os_disk_size_gb=0,  # when == 0 sets default size
            os_type="Linux",
            os_sku="Ubuntu",
            type="VirtualMachineScaleSets",
            vm_size="Standard_B2als_v2",
        ),
    ],
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
        network_dataplane="cilium",
        network_plugin="azure",
        network_policy="cilium",
    ),
    opts=pulumi.ResourceOptions(replace_on_changes=["agent_pool_profiles"]),
)

admin_credentials = containerservice.list_managed_cluster_admin_credentials_output(
    resource_group_name=resource_group.name, resource_name=managed_cluster.name
)

longhorn_storage = k8s.yaml.ConfigFile(
    "longhorn-storage",
    file="https://raw.githubusercontent.com/longhorn/longhorn/v1.8.1/deploy/longhorn.yaml",
)

pulumi.export(
    "kubeconfig",
    admin_credentials.kubeconfigs.apply(get_kubeconfig),
)
