(deploy-configuration)=
# Configuration Reference

This page lists the Pulumi configuration keys used by each FRIDGE stack, and the outputs that one stack consumes from another.

Configuration is stored per stack in `Pulumi.<stack-name>.yaml` and can be edited by hand or set with `pulumi config set`.
Keys marked as **secret** must be set with the `--secret` flag, for example:

```console
pulumi config set --secret harbor_admin_password <value>
```

The stacks must be deployed in this order, as each depends on outputs from the previous one:

1. [Infrastructure](#config-infrastructure) (`infra/aks`, AKS only)
2. [Access cluster](#config-access)
3. [Isolated cluster](#config-isolated)
4. [Network lockdown](#config-lockdown) (`infra/aks-post-deployment`, AKS only)

On Dawn and Zenith, the clusters are created outside Pulumi and the infrastructure and lockdown stacks do not apply.

(config-infrastructure)=
## Infrastructure (`infra/aks`)

Project `fridge_aks`.
Creates the resource group, networking, Key Vault and the two AKS clusters.

| Key | Required | Default | Description |
|---|---|---|---|
| `azure-native:location` | Yes | | Azure region, for example `uksouth` |
| `azure-native:subscriptionId` | Yes | | Azure subscription ID |
| `azure-native:tenantId` | Yes | | Azure tenant ID |
| `resource_group_name` | Yes | | Name of the resource group to create the clusters in |
| `cluster_name` | Yes | | Base name of the clusters. `-access` and `-isolated` are appended |
| `access_vnet_cidr` | No | `10.10.0.0/16` | CIDR of the access cluster VNet |
| `access_nodes_subnet_cidr` | No | `10.10.1.0/24` | CIDR of the access cluster nodes subnet |
| `isolated_vnet_cidr` | No | `10.20.0.0/16` | CIDR of the isolated cluster VNet |
| `isolated_nodes_subnet_cidr` | No | `10.20.1.0/24` | CIDR of the isolated cluster nodes subnet |
| `admin_ip_allowlist` | Yes | | List of IP addresses or ranges allowed to administer the clusters. It is exported as an output |

The stack outputs the kubeconfig for each cluster, the network CIDRs, names and IDs, the NSG names and IDs, the route table, and the isolated cluster API server FQDN and IP (`isolated_cluster_api_server_fqdn` and `isolated_cluster_api_server_ip`).

(config-access)=
## Access cluster (`infra/fridge/access-cluster`)

Project `fridge-access`.
Deploys ingress, cert-manager, Harbor and the NetBird/HAProxy VPN server.

| Key | Required | Secret | Description |
|---|---|---|---|
| `k8s_env` | Yes | | Cluster environment: `AKS`, `Dawn` or `Zenith` |
| `base_fqdn` | Yes | | Base domain for the deployment. Harbor is served at `<harbor_fqdn_prefix>.<base_fqdn>` |
| `harbor_fqdn_prefix` | Yes | | Host name prefix for Harbor |
| `harbor_admin_password` | Yes | Yes | Harbor admin password |
| `harbor_registry_size` | No | | Size of Harbor's registry storage, for example `50Gi`. Defaults to `20Gi`. Large images, such as GPU builds of PyTorch, may need more |
| `tls_environment` | Yes | | Certificate issuer: `staging` or `production` (Let's Encrypt), or `development` (self-signed CA) |
| `lets_encrypt_email` | Yes | | Email address for Let's Encrypt registration. Only read when using Let's Encrypt, but declared as required |
| `fridge_api_ip_address` | Yes | | IP address of the FRIDGE API in the isolated cluster. Used for the HAProxy backend, the network policies and as an output. On AKS this is the same address as `fridge_api_ip` in the isolated stack |
| `isolated_cluster_api_endpoint` | Yes | | Host name or IP address of the isolated cluster's Kubernetes API server. On AKS use `isolated_cluster_api_server_fqdn` from the infrastructure stack |
| `harbor_ip` | Yes | | IP address of Harbor as seen from the cluster nodes. Used to configure containerd to pull from Harbor |
| `azure_subscription_id` | AKS only | | Azure subscription ID. Use a dummy value on Dawn and Zenith |
| `azure_resource_group` | AKS only | | Azure resource group. Use a dummy value on Dawn and Zenith |
| `azure_disk_encryption_set` | AKS only | | Name of the disk encryption set used for the storage class. Use a dummy value on Dawn and Zenith |
| `dawn_load_balancer_ip` | Dawn and Zenith only | | Load balancer IP of the access cluster, used as the Harbor IP. Despite the name, it is also read on Zenith. Use a dummy value on AKS |
| `kubernetes:context` | Yes | | kubectl context of the access cluster |
| `netbird.*` | Yes | | NetBird settings, described below |

### NetBird

These are set as fields of the `netbird` object.
See [Configuring NetBird](./netbird.md) for how to obtain a setup key and configure the NetBird side.

| Key | Required | Secret | Description |
|---|---|---|---|
| `netbird.hostname` | Yes | | Peer name of the access cluster in NetBird |
| `netbird.setup_key` | Yes | Yes | Setup key used to register the peer |
| `netbird.management_url` | No | | Management URL. Defaults to NetBird Cloud, `https://api.netbird.io` |
| `netbird.endpoint_overrides.signal` | No | | Signal server host, for self-hosted NetBird |
| `netbird.endpoint_overrides.stun` | No | | STUN server host, for self-hosted NetBird |
| `netbird.endpoint_overrides.relay` | No | | Relay server host, for self-hosted NetBird |
| `netbird.endpoint_overrides.turn` | No | | TURN server host, for self-hosted NetBird |

The overrides are only needed when running a self-hosted NetBird whose servers are on different hosts from the management server.
The network policies allow egress to the management host and, if set, the override hosts.

### Outputs

| Output | Description |
|---|---|
| `fridge_api_ip_address` | Echo of the configuration value |
| `harbor_fqdn` | Fully qualified domain name of Harbor |
| `harbor_ca_bundle` | CA certificates needed to verify Harbor's certificate: the self-signed CA when `tls_environment` is `development`, or the Let's Encrypt staging roots when it is `staging`. Not exported when `tls_environment` is `production`, as the system trust store is sufficient |
| `harbor_ip_address`, `ingress_ip`, `ingress_ports` | AKS only |

(config-isolated)=
## Isolated cluster (`infra/fridge/isolated-cluster`)

Project `fridge-isolated`.
Deploys Argo Workflows, SeaweedFS object storage, block storage, the FRIDGE API and supporting services.
It reads outputs from the access cluster stack, so the access cluster must be deployed first.

| Key | Required | Secret | Description |
|---|---|---|---|
| `k8s_env` | Yes | | Cluster environment: `AKS`, `Dawn` or `Zenith` |
| `organization_name` | No | | Pulumi organisation that owns the access cluster stack. Defaults to `organization`, which is correct for any backend other than Pulumi Cloud. On Pulumi Cloud, set it to your organisation name |
| `project_name` | No | | Pulumi project name of the access cluster stack. Defaults to `fridge-access`. Only change it if the access cluster was deployed under a different project name |
| `access_cluster_stack` | Yes | | Name of the access cluster stack |
| `base_fqdn` | Yes | | Base domain for the deployment. Used for the self-signed CA certificate |
| `fridge_api_admin` | Yes | Yes | Username for the FRIDGE API |
| `fridge_api_password` | Yes | Yes | Password for the FRIDGE API |
| `fridge_api_ip` | AKS only | | Fixed IP address for the FRIDGE API's internal load balancer. Must be in the isolated nodes subnet. Not used on Dawn or Zenith, where the API is exposed on NodePort 30180 |
| `s3_access_key` | Yes | Yes | Access key of the FRIDGE API's generic S3 identity. This identity can only upload to, list and delete from the `ingress` bucket, and read and list the `egress` bucket |
| `s3_secret_key` | Yes | Yes | Secret key of the FRIDGE API's generic S3 identity |
| `s3_admin_access_key` | Yes | Yes | Access key of the S3 admin identity (`fridge-admin`). Used by the bucket setup job, and supplied by admins to the FRIDGE API for admin operations such as creating buckets. It is never given to the API itself |
| `s3_admin_secret_key` | Yes | Yes | Secret key of the S3 admin identity |
| `block_storage_size` | Yes | | Size of the block storage volume shared with workflows, for example `100Gi` |
| `seaweedfs.root_user` | Yes | Yes | SeaweedFS root user |
| `seaweedfs.root_password` | Yes | Yes | SeaweedFS root password |
| `seaweedfs.pool_size` | Yes | | Size of the SeaweedFS storage pool. Must be a valid Kubernetes quantity, for example `40Gi` |
| `run_tests` | No | | Set to `true` to deploy the example GPU test workflow templates: Intel GPU examples on Dawn, AMD GPU examples on Zenith. Ignored on AKS. Defaults to `false` |
| `azure_subscription_id` | AKS only | | Azure subscription ID. Use a dummy value on Dawn and Zenith |
| `azure_resource_group` | AKS only | | Azure resource group. Use a dummy value on Dawn and Zenith |
| `azure_disk_encryption_set` | AKS only | | Name of the disk encryption set used for the storage class. Use a dummy value on Dawn and Zenith |
| `access_cluster_load_balancer_ip` | Dawn and Zenith only | | Load balancer IP of the access cluster. Used to resolve the Harbor host name on the nodes |
| `kubernetes:context` | Yes | | kubectl context of the isolated cluster |

`seaweedfs` is a single object, so set its fields using `--path`:

```console
pulumi config set --secret --path seaweedfs.root_password <value>
pulumi config set --path seaweedfs.pool_size 40Gi
```

### Inputs from the access cluster stack

The isolated stack reads these outputs from the access cluster stack: `fridge_api_ip_address`, `harbor_fqdn` and `harbor_ca_bundle`.
If `harbor_ca_bundle` is not exported, containerd on the isolated cluster nodes uses the system trust store to verify Harbor's certificate.

### Outputs

| Output | Description |
|---|---|
| `fridge_api_ip` | Echo of the configuration value. AKS only |

(config-lockdown)=
## Network lockdown (`infra/aks-post-deployment`)

Project `fridge-lockdown`, AKS only.
Adds a firewall and tightens the network security rules once both clusters are deployed.
It reads outputs from the infrastructure stack and both cluster stacks, so it must be deployed last.

All of the keys below are required.

| Key | Description |
|---|---|
| `azure-native:location` | Azure region |
| `azure_resource_group` | Resource group containing the clusters, as set in the infrastructure stack |
| `organization_name` | Pulumi organisation that owns the other stacks |
| `project_name` | Pulumi project name of the infrastructure stack (`fridge_aks`) |
| `infrastructure_stack_name` | Name of the infrastructure stack |
| `access_cluster_stack_name` | Name of the access cluster stack |
| `isolated_cluster_stack_name` | Name of the isolated cluster stack |

The access and isolated cluster project names are fixed in the code as `fridge-access` and `fridge-isolated`, so the stacks must belong to projects with those names.

:::{warning}
The private DNS zone created by this project is currently fixed to `aks-dual.fridge.develop.turingsafehaven.ac.uk`.
It is not configurable.
:::
