# A minimal cluster on Azure

These steps allow you to deploy a minimal AKS cluster on Azure with a single VM that allows RDP access.

## Step 1 - Create an AKS cluster

Create a resource group using Azure CLI.

```bash
az group create --name YOUR_RESOURCE_GROUP --location YOUR_LOCATION
```

Create an AKS cluster using Azure CLI. This example includes some additional flags that correspond to some most parts of the Azure provided defaults for dev/test AKS clusters.

```bash
az aks create --resource-group YOUR_RESOURCE_GROUP --name YOUR_CLUSTER_NAME --node-count 2 --nodepool-name YOUR_SYSTEM_POOL_NAME --auto-upgrade-channel node-image --enable-cluster-autoscaler --min-count 2 --max-count 5 --node-vm-size Standard_D4ds_v5 --enable-oidc-issuer --api-server-authorized-ip-ranges xxx.xxx.xxx.xxx
```

Some of the potential options that may be useful - some of which are setup by default if creating a cluster through the portal - are:

```bash
--auto-upgrade-channel (rapid|stable|patch|node-image|none (node-image is az dev default))
--api-server-authorized-ip-ranges (restricts access to the API server to a specific IP range)
--enable-workload-identity (not clear what this does)
--enable-cluster-autoscaler (allows the cluster to scale number of nodes automatically (not clear how this works as yet, may need additional rules/alerts to be set up))
--enable-image-cleaner (not clear how useful this is for our workflow - cleans up old container images automatically)
--enable-oidc-issuer (may be useful for setting up OAuth)
--node-osdisk-type ephemeral
--node-vm-size -s (Standard_D4ds_v5 is the one that Azure suggests as a default for dev/testing)
--nodepool-name )
--enable-app-routing (can be used to create an Azure managed nginx ingress proxy)
```

By default, this will deploy a k8s cluster with a single `System` node pool, which runs the default k8s resources like its internal `CoreDNS` pod. You can still use this same pool to deploy additional resources if you like, but you may want to add a second `User` pool for other non-system pods (or VMs).

To add a second pool - optional for testing, but probably best practice, use the Az CLI.

```bash
az aks nodepool add --resource-group YOUR_RESOURCE_GROUP --cluster-name YOUR_CLUSTER_NAME --name YOUR_NODE_NAME --node-count 2 --os-sku Ubuntu --max-pods 110 --node-vm-size Standard_D4ds_v5 --enable-cluster-autoscaler --min-count 2 --max-count 5
```

To be able to administer the cluster via the API locally, using `kubectl` for example, use the Azure CLI to obtain the relevant credentials:

```bash
az aks get-credentials --resource-group YOUR_RESOURCE_GROUP --name YOUR_CLUSTER_NAME
```

If you have multiple clusters, you can switch between them using `kubectl`:

```bash
kubectl config use-context YOUR_CLUSTER_NAME
```

## Step 2 - Set up Kubevirt

The first step is to install the `kubevirt-operator`, which manages all the Kubevirt resources that are deployed in the second step.

At the time of writing, the latest version is `v1.4.0`.

```bash
kubectl create -f "https://github.com/kubevirt/kubevirt/releases/download/v1.4.0/kubevirt-operator.yaml"
```

The second step adds custom resources.
This is the step that actually deploys the Kubevirt resources.
An issue for deploying on AKS is that the installation script is looking for nodes with the `control-plane` role, but AKS does not expose the control plane to the user/customer.
The solution is either to label the nodes with the role or to modify the installation script.

A modified installation script is provided in the `kubevirt-customise-cr.yaml` file in this repository.
This script removes the requirement for Kubevirt infrastructure to be deployed on nodes with the `control-plane` role.
In a future iteration, we may want to add a separate node pool for Kubevirt resources and direct Kubevirt to deploy on that pool.

```bash
kubectl apply -f kubevirt-customise-cr.yaml
```

Note that this file is also useful for enabling additional Kubevirt features such as snapshotting or live migration of VMs.
For now, we will leave the additional features disabled.

### Optional/advanced configuration steps

#### Using the default installation script for non-AKS clusters

As an alternative to the modified installation script, the default installation script can be used.

```bash
kubectl create -f "https://github.com/kubevirt/kubevirt/releases/download/v1.4.0/kubevirt-cr.yaml"
```

You can then apply the `control-plane` role to all nodes using `kubectl label nodes`:

```bash
kubectl label nodes --all 'node-role.kubernetes.io/control-plane=control-plane'
```

To be more specific, applying the control plane role only to the `system` node, use

```bash
kubectl label nodes -l 'kubernetes.azure.com/mode=system' 'node-role.kubernetes.io/control-plane=control-plane'
```

Note that by default Kubevirt will make it possible for VMs to be scheduled on all nodes (including system nodes).
This can be changed by modifying the `kubevirt-customise-cr.yaml` file.
The field `workloads` can be added to the `spec` section of the `Kubevirt` resource, with the subfield `nodePlacement` to specify which nodes VMs can be scheduled on.

See https://kubevirt.io/user-guide/cluster_admin/installation/#restricting-kubevirt-components-node-placement for more information.

## Step 3 - Deploy a VM

### Deploy Containzerized Data Importer

The simplest way to build a VM is to start from a pre-built `containerdisk` image, such as those managed by [kubevirt](https://github.com/kubevirt/containerdisks)
The images they use include only a very small OS disk, so we need to find a way to expand it.
One such way is to use `DataVolumes`. Container disks can be mounted in a `DataVolume`.

The method is described in a [Github issue](https://github.com/kubevirt/kubevirt/issues/3130) on the Kubevirt repo.

First, we need to install `Containerized Data Importer` - see https://kubevirt.io/user-guide/storage/containerized_data_importer/

This is an extension that allows you to use `DataVolumes`, which can hold VM images in a `PersistentVolumeClaim` with a given disk size. The container image then expands to use the full disk size of the PVC.

These can then be used to launch VMs.

The latest release of CDI is found at https://github.com/kubevirt/containerized-data-importer/releases/latest

To install it, run the following:

```bash
kubectl create -f https://github.com/kubevirt/containerized-data-importer/releases/download/v1.61.2/cdi-operator.yaml
kubectl create -f https://github.com/kubevirt/containerized-data-importer/releases/download/v1.61.2/cdi-cr.yaml
```

### Deploy a VM from a yaml file

Define the VM using a `yaml` file. An example is supplied in `ubuntu-desktop.yaml`

```bash
kubectl apply -f ubuntu-desktop.yaml
```

This example creates an Ubuntu 22.04 server with xfce4 and xrdp installed. It is deployed in a stopped state and needs to be manually started, but that can be modified by the `runStrategy` field in the `yaml` file.

Note that this deploys to the `default` namespace. We may want to add a separate namespace for VMs.

### Deploy a VM using `helm`


`virtctl` can be used to manage VMs once they are on the cluster. `virtctl` can be downloaded from the Kubevirt Github repo (see the [Kubevirt](https://kubevirt.io/user-guide/user_workloads/virtctl_client_tool/) site):

```bash
curl -L -o virtctl <https://github.com/kubevirt/kubevirt/releases/download/v1.4.0/virtctl-v1.4.0-darwin-arm64>
chmod +x virtctl
```

To start the VM, run

```bash
virtctl start ubuntu-desktop
```

To get a shell on the VM, use:

```bash
virtctl console ubuntu-desktop
```

From there, you may want to add additional users to test out RDP access.

## Step 4 - Deploy guacamole

First, set up a separate namespace for guacamole. Note this is not *necessary* but does help with organization and may allow us to apply more specific policies to Guacamole at a later date.

Create a guacamole namespace using a yaml file structured as below, or directly with `kubectl`

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: guac
```

```bash
kubectl create namespace guac
```

### Helm charts

We can use existing Helm charts rather than define our own `yaml` files.

A `postgresql` database needs to be set up first:

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install postgresql bitnami/postgresql \
 --set auth.username=guacamole \
 --set auth.password=password \
 --set auth.postgresPassword=password \
 --set auth.database=guacamole --wait \
 --namespace guac
```

Afterwards, we can set up Guacamole.

```bash
helm repo add beryju https://charts.beryju.io
helm install guacamole beryju/guacamole --namespace guac
```

### Making guacamole accessible

Guacamole can be accessed locally using port forwarding.

```bash
kubectl port-forward deployment/guacamole-guacamole :8080 -n guac
```

This allows you to access the guacamole server from a random local port, which will be shown in the command's output, as below:

```none
Forwarding from 127.0.0.1:59292 -> 8080
Forwarding from [::1]:59292 -> 8080
```

Guacamole can then be accessed through a browser at `localhost:<your_port_here>`.

To make it accessible to the wider world, deploying a load balancer is the easiest starting point.

This can be done either with the provided `.yaml` file or using `kubectl`. E.g. to expose the guacamole server on port 80, use the following:

```bash
kubectl expose deployment guacamole-guacamole -n guac --port=80 --target-port=8080 --name=guac-lb --type=LoadBalancer
```

Alternatively, we can set up ingress on AKS (not yet tested!) - see https://learn.microsoft.com/en-us/azure/aks/app-routing.

Once you have access to `guacamole`, you can add connections manually.

You will need to enter the IP address of the VM as the hostname for the server, which you can find using `kubectl`:

```bash
kubectl get vmi
```

Pods and services receive local DNS names automatically - e.g. a pod called `guac` in the default namespace would be `guac.default.cluster.local` - but VMs do not.
We should either find a way to add them, as the IP address might change if the VM is stopped/started again, or add a service for the VM that will have one automatically.
