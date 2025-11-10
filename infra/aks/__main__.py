import base64

import components
import pulumi
import pulumi_random as random
import pulumi_tls as tls
from pulumi_azure_native import (
    authorization,
    compute,
    containerservice,
    keyvault,
    managedidentity,
    resources,
)


def get_kubeconfig(
    credentials: list[containerservice.outputs.CredentialResultResponse],
) -> str | None:
    for credential in credentials:
        if credential.name == "clusterAdmin":
            return base64.b64decode(credential.value).decode()


config = pulumi.Config()
azure_config = pulumi.Config("azure-native")

resource_group = resources.ResourceGroup(
    "resource_group",
    resource_group_name=config.require("resource_group_name"),
)

ssh_key = tls.PrivateKey("ssh-key", algorithm="RSA", rsa_bits="3072")

suffix = random.RandomString(
    "suffix", length=8, lower=True, numeric=True, special=False
)

kv = keyvault.Vault(
    "keyvault",
    vault_name=pulumi.Output.concat("fridge-kv-", suffix.result),
    properties=keyvault.VaultPropertiesArgs(
        # To use this keyvault for BYOK, it requires vault authorisation (not RBAC),
        # purge protection and soft delete
        enable_purge_protection=True,
        enable_rbac_authorization=False,
        enable_soft_delete=True,
        sku=keyvault.SkuArgs(
            family=keyvault.SkuFamily.A,
            name=keyvault.SkuName.STANDARD,
        ),
        soft_delete_retention_in_days=90,
        tenant_id=azure_config.require("tenantId"),
    ),
    resource_group_name=resource_group.name,
)

disk_encryption_key = keyvault.Key(
    "disk-encryption-key",
    key_name="fridge-pvc-key",
    resource_group_name=resource_group.name,
    vault_name=kv.name,
    properties=keyvault.KeyPropertiesArgs(
        key_size=2048,
        kty=keyvault.JsonWebKeyType.RSA,
    ),
)

disk_encryption_set = compute.DiskEncryptionSet(
    "disk-encryption-set",
    resource_group_name=resource_group.name,
    disk_encryption_set_name="fridge-disk-encryption-set",
    active_key=compute.KeyForDiskEncryptionSetArgs(
        key_url=disk_encryption_key.key_uri_with_version,
    ),
    encryption_type=compute.DiskEncryptionSetType.ENCRYPTION_AT_REST_WITH_CUSTOMER_KEY,
    identity=compute.EncryptionSetIdentityArgs(
        type=compute.DiskEncryptionSetIdentityType.SYSTEM_ASSIGNED,
    ),
)

# Grant disk encryption set permission to use keyvault keys
access_policy = keyvault.AccessPolicy(
    "access-policy",
    vault_name=kv.name,
    resource_group_name=resource_group.name,
    policy=keyvault.AccessPolicyEntryArgs(
        object_id=disk_encryption_set.identity.principal_id,
        tenant_id=azure_config.require("tenantId"),
        permissions=keyvault.PermissionsArgs(
            keys=[
                keyvault.KeyPermissions.UNWRAP_KEY,
                keyvault.KeyPermissions.WRAP_KEY,
                keyvault.KeyPermissions.GET,
            ],
        ),
    ),
)

# AKS cluster
identity = managedidentity.UserAssignedIdentity(
    "cluster_managed_identity",
    resource_group_name=resource_group.name,
)

authorization.RoleAssignment(
    "cluster_role_assignment_disk_encryption_set",
    principal_id=identity.principal_id,
    principal_type=authorization.PrincipalType.SERVICE_PRINCIPAL,
    # Contributor: https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles
    role_definition_id=f"/subscriptions/{azure_config.require('subscriptionId')}/providers/Microsoft.Authorization/roleDefinitions/b24988ac-6180-42a0-ab88-20f7382dd24c",
    # The docs suggest using the scope of the resource group where the disk encryption
    # set is located. However, the scope of the disk encryption set seems sufficient.
    # Disks are created in the AKS managed resource group
    # https://learn.microsoft.com/en-us/azure/aks/azure-disk-customer-managed-keys#encrypt-your-aks-cluster-data-disk
    # scope=f"/subscriptions/{azure_config.require('subscriptionId')}"
    scope=disk_encryption_set.id,
)

# Networking
networking = components.Networking(
    "networking",
    components.NetworkingArgs(
        config=config,
        resource_group_name=resource_group.name,
        location=resource_group.location,
    ),
)

# Grant the managed identity Contributor role on the isolated vnet so it can manage network interfaces
# This allows the creation of internal load balancers to make it easier to direct traffic to the right place on the isolated network
authorization.RoleAssignment(
    "cluster_role_assignment_isolated_vnet",
    principal_id=identity.principal_id,
    principal_type=authorization.PrincipalType.SERVICE_PRINCIPAL,
    # Contributor: https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles
    role_definition_id=f"/subscriptions/{azure_config.require('subscriptionId')}/providers/Microsoft.Authorization/roleDefinitions/b24988ac-6180-42a0-ab88-20f7382dd24c",
    scope=networking.isolated_nodes.id,
)

# Create isolated cluster to host private workloads
isolated_cluster = components.IsolatedCluster(
    "isolated-cluster",
    components.IsolatedClusterArgs(
        config=config,
        disk_encryption_set=disk_encryption_set,
        resource_group_name=resource_group.name,
        cluster_name=f"{config.require('cluster_name')}-isolated",
        identity=identity,
        nodes_subnet_id=networking.isolated_nodes_subnet_id,
        ssh_key=ssh_key,
    ),
)

isolated_admin_credentials = (
    containerservice.list_managed_cluster_admin_credentials_output(
        resource_group_name=resource_group.name, resource_name=isolated_cluster.name
    )
)

# Create access cluster

# This is a public facing cluster that will run proxies to the private cluster

access_cluster = components.AccessCluster(
    "access-cluster",
    components.AccessClusterArgs(
        config=config,
        resource_group_name=resource_group.name,
        cluster_name=f"{config.require('cluster_name')}-access",
        identity=identity,
        nodes_subnet_id=networking.access_nodes_subnet_id,
        ssh_key=ssh_key,
    ),
)

access_admin_credentials = (
    containerservice.list_managed_cluster_admin_credentials_output(
        resource_group_name=resource_group.name, resource_name=access_cluster.name
    )
)

isolated_kubeconfig = isolated_admin_credentials.kubeconfigs.apply(get_kubeconfig)
access_kubeconfig = access_admin_credentials.kubeconfigs.apply(get_kubeconfig)

pulumi.export("access_kubeconfig", access_kubeconfig)
pulumi.export("access_nodes_subnet_cidr", networking.access_nodes.address_prefix)
pulumi.export("access_subnet_nsg", networking.access_nsg)
pulumi.export("isolated_cluster_api_server_fqdn", isolated_cluster.fqdn)
pulumi.export("isolated_kubeconfig", isolated_kubeconfig)
pulumi.export("isolated_nodes_subnet_cidr", networking.isolated_nodes.address_prefix)
pulumi.export("isolated_subnet_nsg", networking.isolated_nsg)
