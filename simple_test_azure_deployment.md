# Creating a test deployment on Azure

This document outlines the steps to create a test deployment on Azure, using Azure Kubernetes Service (AKS) and Kubevirt.

## Step 1 - Create an Azure Kubernetes cluster

Create a virtual environment and install the dependencies.

```console
cd infra/azure
python3 -m venv ./venv
source ./venv/bin/activate
pip install -r requirements.txt
```

Create a stack.

```console
pulumi stack init dev
cp Pulumi.dev.yaml.template Pulumi.dev.yaml
```

Authenticate with az CLI, then deploy the resources with Pulumi.

```console
az login
pulumi preview
pulumi up
```

Export the kubeconfig from Pulumi outputs and use it for kubectl.

```console
pulumi stack output kubeconfig > kubeconfig.yaml
export KUBECONFIG=$PWD/kubeconfig.yaml
```

Or,

```console
pulumi stack output kubeconfig > ~/.kube/config
```

You can now use `kubectl` to interact with the cluster

```console
kubectl get nodes
kubectl get nodes -l agentpool=gppool
```

## Step 2 - Set up Kubevirt

The first step is to install the `kubevirt-operator`, which manages all the Kubevirt resources that are deployed in the second step.

At the time of writing, the latest version is `v1.4.0`.

```console
kubectl create -f "https://github.com/kubevirt/kubevirt/releases/download/v1.4.0/kubevirt-operator.yaml"
```

The second step adds custom resources.
This is the step that actually deploys the Kubevirt resources.
An issue for deploying on AKS is that the installation script is looking for nodes with the `control-plane` role, but AKS does not expose the control plane to the user/customer.
The solution is either to label the nodes with the role or to modify the installation script.

A modified installation script is provided in the `kubevirt-customise-cr.yaml` file in this repository.
This script removes the requirement for Kubevirt infrastructure to be deployed on nodes with the `control-plane` role.
In a future iteration, we may want to add a separate node pool for Kubevirt resources and direct Kubevirt to deploy on that pool.

```console
kubectl apply -f kv-customise-cr.yaml
```

Note that this file is also useful for enabling additional Kubevirt features such as snapshotting or live migration of VMs.
For now, we will leave the additional features disabled.

### Optional/advanced configuration steps

#### Using the default installation script for non-AKS clusters

As an alternative to the modified installation script, the default installation script can be used.

```console
kubectl create -f "https://github.com/kubevirt/kubevirt/releases/download/v1.4.0/kubevirt-cr.yaml"
```

You can then apply the `control-plane` role to all nodes using `kubectl label nodes`:

```console
kubectl label nodes --all 'node-role.kubernetes.io/control-plane=control-plane'
```

To be more specific, applying the control plane role only to the `system` node, use

```console
kubectl label nodes -l 'kubernetes.azure.com/mode=system' 'node-role.kubernetes.io/control-plane=control-plane'
```

Note that by default Kubevirt will make it possible for VMs to be scheduled on all nodes (including system nodes).
This can be changed by modifying the `kv-customise-cr.yaml` file.
The field `workloads` can be added to the `spec` section of the `Kubevirt` resource, with the subfield `nodePlacement` to specify which nodes VMs can be scheduled on.

See <https://kubevirt.io/user-guide/cluster_admin/installation/#restricting-kubevirt-components-node-placement> for more information.

## Step 3 - Deploy Longhorn

We want shared storage that will be accessible to multiple VMs.
The VMs deployed in subsequent steps assume a Longhorn volume is available.

[Longhorn](https://longhorn.io/) is a distributed block storage system for Kubernetes. It is a Cloud Native Computing Foundation (CNCF) Sandbox project.

Longhorn allows you to create volumes on the disks attached to the nodes in your cluster. These volumes can be used to store data that needs to persist between pod restarts or to share data between pods.

To install Longhorn, run the following command:

```console
kubectl apply -f "https://raw.githubusercontent.com/longhorn/longhorn/v1.8.1/deploy/longhorn.yaml"
```

To access the Longhorn UI, you can either use `kubectl port-forward` or expose the service using a LoadBalancer. For example, to expose the Longhorn UI on port 8000, run the following command:

```console
kubectl port-forward svc/longhorn-frontend 8000:80 -n longhorn-system
```

Then `http://localhost:8000` in your browser will take you to the Longhorn UI.

From there, you can create volumes that can be attached to VMs.

The following is an example of a PersistentVolumeClaim (PVC) that can be used to create a volume in Longhorn:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: longhorn-volv-pvc
spec:
  accessModes:
    - ReadWriteMany
  storageClassName: longhorn
  resources:
    requests:
      storage: 20Gi
```

For this test deployment, we will use Longhorn as the storage backend for the VMs and deploy a drive using a YAML file.

```console
kubectl apply -f longhorn-drive.yaml
```

Note that this drive is initially unformatted.

## Step 4 - Deploy a VM

We'll now deploy an Ubuntu VM using Kubevirt.

### Deploy Containerized Data Importer

The simplest way to build a VM is to start from a pre-built `containerdisk` image, such as those managed by [Kubevirt](https://github.com/kubevirt/containerdisks)
The images they use include only a very small OS disk, so we need to find a way to expand it.
One such way is to use `DataVolumes`. Container disks can be mounted in a `DataVolume`.
The method is described in a [Github issue](https://github.com/kubevirt/kubevirt/issues/3130) on the Kubevirt repo.

First, we need to install `Containerized Data Importer` - see https://kubevirt.io/user-guide/storage/containerized_data_importer/

This is an extension that allows you to use `DataVolumes`, which can hold VM images in a `PersistentVolumeClaim` with a given disk size. The container image then expands to use the full disk size of the PVC.

These can then be used to launch VMs.

The latest release of CDI is found at https://github.com/kubevirt/containerized-data-importer/releases/latest

To install it, run the following:

```console
kubectl create -f https://github.com/kubevirt/containerized-data-importer/releases/download/v1.61.2/cdi-operator.yaml
kubectl create -f https://github.com/kubevirt/containerized-data-importer/releases/download/v1.61.2/cdi-cr.yaml
```

### Deploy a VM from a yaml file

Define the VM using a `yaml` file. An example is supplied in `ubuntu-desktop.yaml`

```console
kubectl apply -f ubuntu-desktop.yaml
```

This example creates an Ubuntu 22.04 server with `xfce4` and `xrdp` installed. It is deployed in a stopped state and needs to be manually started, but that can be modified by the `runStrategy` field in the `yaml` file.

Note that this deploys to the `default` namespace. We may want to add a separate namespace for VMs.

A service exposing port 3389 is also created, which can be used to access the VM via RDP.

### Deploy a VM using `helm`

A `helm` chart is available in this repo for deploying VMs.
By default, this creates a single VM running Ubuntu 22.04, with a 30GB disk, 2GB of RAM, and 2 CPUs.
The specific configuration can be modified either using the included `values.yaml` file or by passing in values at deployment time.
As above, it will also have `xfce4` and `xrdp` installed.
The VM is deployed in a stopped state and needs to be manually started.
A service exposing the RDP port is also created.

```console
helm install ubuntu-desktop ./kv-single-vm
```

### Managing VMs using `virtctl`

`virtctl` can be used to manage VMs once they are on the cluster. `virtctl` can be downloaded from the Kubevirt Github repo (see the [Kubevirt](https://kubevirt.io/user-guide/user_workloads/virtctl_client_tool/) site):

```console
curl -L -o virtctl <https://github.com/kubevirt/kubevirt/releases/download/v1.4.0/virtctl-v1.4.0-darwin-arm64>
chmod +x virtctl
```

To start the VM, run

```console
virtctl start ubuntu-desktop
```

To get a shell on the VM, use:

```console
virtctl console ubuntu-desktop
```

From there, you may want to add additional users to test out RDP access.

In addition, if you want to use the shared Longhorn volume, you will need to format and mount it manually from the console.
Note: it only needs to be formatted once!

## Step 5 - Deploy guacamole

First, set up a separate namespace for guacamole. Note this is not *necessary* but does help with organization and may allow us to apply more specific policies to Guacamole at a later date.

Create a guacamole namespace using a yaml file structured as below, or directly with `kubectl`

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: guac
```

```console
kubectl create namespace guac
```

### Helm charts

We can use existing Helm charts rather than define our own `yaml` files.

A `postgresql` database needs to be set up first:

```console
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install postgresql bitnami/postgresql \
 --set auth.username=guacamole \
 --set auth.password=password \
 --set auth.postgresPassword=password \
 --set auth.database=guacamole --wait \
 --namespace guac
```

Afterwards, we can set up Guacamole.

```console
helm repo add beryju https://charts.beryju.io
helm install guacamole beryju/guacamole --namespace guac
```

### Making guacamole accessible

Guacamole can be accessed locally using port forwarding.

```console
kubectl port-forward deployment/guacamole-guacamole 8080:8080 -n guac
```

This allows you to access the guacamole server on port 8080, which will be shown in the command's output, as below:

Guacamole can then be accessed through a browser at `localhost:8080`.

To make it accessible to the wider world, deploying a load balancer is the easiest starting point.

This can be done either with the provided `.yaml` file or using `kubectl`. E.g. to expose the guacamole server on port 80, use the following:

```console
kubectl expose deployment guacamole-guacamole -n guac --port=80 --target-port=8080 --name=guac-lb --type=LoadBalancer
```

Alternatively, we can set up managed Nginx ingress on AKS (not yet tested!) - see https://learn.microsoft.com/en-us/azure/aks/app-routing.

Once you have access to `guacamole`, you can add connections manually.

You will need to enter the IP address of the VM as the hostname for the server, which you can find using `kubectl`:

```console
kubectl get vmi
```

Pods and services receive local DNS names automatically - e.g. a pod called `guac` in the default namespace would be `guac.default.pod.cluster.local` - but VMs do not.
We add a service for each VM to provide easy connectivity.
