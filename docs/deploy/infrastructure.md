# Deploy Infrastructure

:::{seealso}
To read about deploying the services on top of the Kubernetes clusters see [Deploy Services](./services.md).
:::

This page explains how to deploy the Kubernetes clusters for FRIDGE using Pulumi, and how to lock them down after deployment of the FRIDGE services.

## Azure Kubernetes Service (AKS)

The FRIDGE infrastructure can be deployed to Azure using the Azure Kubernetes Service (AKS).

An example Pulumi project for deploying FRIDGE to AKS is available in the `fridge/infra/aks/` folder.

To succesfully deploy the project, you will require an Azure account that has, at minimum, `Contributor` rights over the subscription you will deploy the FRIDGE into.
In addition, this account will need permission to delegate roles to the managed identity that will manage the FRIDGE clusters.
The deployment process will delegate the role `Network Contributor` scoped to the VNets that the clusters will be hosted on, and `Contributor` scoped to the disk encryption set used to encrypt the disks within the clusters.

This project deploys two AKS clusters: an `access` cluster and an `isolated` cluster.

The `access` cluster will host the Harbor container registry and an SSH server for accessing the `isolated` cluster.and an `isolated` cluster, which will host the main FRIDGE services.

The example project also deploys the necessary networking components.

Each cluster is deployed to its own VNet.
You will need to supply the desired CIDR for each VNet in the Pulumi configuration, and desired subnet within those VNets for the AKS nodes to be deployed to.

Basic Network Security Groups (NSGs) will also be set up for the VNets.

:::{important}
Note that when the `TRE Administrators` deploy FRIDGE services to the access cluster, they will include an SSH server listening on port 2500.

The `TRE Administrators` must supply a range of IP addresses from which the server should accept connections.

The initial Network Security Group setup will restrict incoming traffic on port 2500 to the IP addresses they provide.
:::

### Deploying the AKS infrastructure with Pulumi

To deploy the infrastructure, follow these steps:

1. Create a new Pulumi stack:

```console
pulumi stack init <stack-name>
```

1. Configure the stack with the necessary settings, such as the Azure region, resource group name, and SSH public key:

```console
pulumi config set azure:location <region>
pulumi config set resource_group_name <resource-group-name>
pulumi config set ssh_public_key "<your-ssh-public-key>"
```

:::{important}
The provided `Pulumi.yaml` provides the schema to follow for the Pulumi configuration file
:::

1. Deploy the infrastructure:

```console
pulumi up
```

Note that for development and testing, the `access` cluster has a public API server endpoint.
In production, it would be private and accessed via a bastion.

The `isolated` cluster has a private API server endpoint, which will be made accessible only from within the access cluster.

When the infrastructure has finished deploying, you should provide the TRE Administrators reponsible for deploying FRIDGE with the necessary connection details, including the public IP address of the Kubernetes cluster, and credentials for the two clusters.

## Dawn AI

Deployment on Dawn is currently a partly manual, partly Pulumi based process.

The `fridge/infra/dawn/` directory contains Pulumi code for the deployment of the initial networking setup and nodes for use by Kubernetes.

On Dawn, [K3s](https://k3s.io/) is the Kubernetes distribution of choice.

The deployment of two K3s clusters onto the associated nodes should be completed manually.

Once setup is complete, you should provide the TRE Administrators with the following:

- public IP address of bastion host for accessing the access cluster
- Kubernetes credentials for the access and isolated clusters
- internal and external IP addresses of the load balancer on the access cluster

The TRE Adminstrators responsible for deploying the FRIDGE services will require this information.

## Network lockdown

Once the TRE Administrators have completed deployment of the FRIDGE services to the access and isolated clusters, it is the responsibility of the Hosting Provider Administrators to complete a final network lockdown.

The final lockdown step ensures that:
1. outbound network traffic from the isolated cluster is only permitted to the container registry hosted in the access cluster
1. inbound traffic to the isolated cluster is only allowed from the access cluster to the FRIDGE API and private Kubernetes API

The isolated cluster is not isolated from the internet until this is completed.

Example Pulumi code for locking down AKS after FRIDGE deployment can be found at `fridge/infra/aks-post-deployment`.

For AKS, this involves making changes to the network security groups for the VNets on which the two clusters are hosted, and setting up a private DNS zone with a record for Harbor, pointing its FQDN towards its internal IP address.

On Dawn, a similar process involves removal of the network router allowing the isolated cluster's VNet direct access to the internet, and modifying the security group rules governing traffic between the two VNets.
