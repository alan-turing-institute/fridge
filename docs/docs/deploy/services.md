# Deploy Services

This page explains how to deploy the FRIDGE services to a FRIDGE tenancy.
This process includes configuration for various components such as Argo Workflows, MinIO, network policies, and other infrastructure settings.
It does not deploy the Kubernetes clusters within the FRIDGE tenancy; instead, it assumes that Kubernetes clusters have already been deployed.

!!! note
    To read about deploying the required Kubernetes clusters see [Deploy Infrastructure](./infrastructure.md).

!!! warning
    Container-based Kubernetes environments such as K3d or Kind are not supported, as Longhorn is not compatible with those environments.

## Deployment

A FRIDGE consists of two Kubernetes clusters: an access cluster and an isolated cluster.
The access cluster hosts the Harbor container registry and an SSH server for accessing the isolated cluster.
The isolated cluster hosts the FRIDGE services.
The deployment process uses Pulumi to manage the infrastructure as code.
You will require appropriate Kubernetes contexts set up for both clusters.

!!! note
    The following instructions assume you have already deployed the Kubernetes clusters using the instructions in [Deploy Infrastructure](./infrastructure.md).
    They are based on the AKS deployment example, and will be updated when the instructions for deploying to DAWN AI are available.

### Pulumi Backend

You can use any backend you like for Pulumi.
The [Pulumi documentation](https://www.pulumi.com/docs/iac/concepts/state-and-backends/) details how to use various backends.
For local development and testing, you can use the local backend:

```console
pulumi login --local
```

### Access cluster

First, navigate to the `infra/fridge-dual-cluster/access-cluster/` folder.
You will deploy the access cluster first, as it hosts the Harbor container registry and SSH server required to access the isolated cluster.

### Virtual Environment

Set up a virtual environment for this project.
You can use the following commands:

```console
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Creating a stack

The `infra/fridge-dual-cluster/access-cluster/` folder already contains a Pulumi project configuration file (`Pulumi.yaml`), so you do not need to run `pulumi new` to create a new project.
The `Pulumi.yaml` file defines the project name and a schema for the configurations for individual stacks.

To create a new stack, you can use the following command:

```console
pulumi stack init <stack-name>
```

!!! note
    You will be asked to provide a passphrase for the stack, which is used to encrypt secrets within the stack's configuration settings.

### Configuring your stack

Each stack has its own configuration settings, defined in the `Pulumi.<stack-name>.yaml` files.
The configuration can be manually edited, or you can use the Pulumi CLI to set configuration values.
You can set individual configuration values for the stack using the following command:

```console
pulumi config set <key> <value>
```

Some of the configuration keys must be set as secrets, such as the MinIO access key and secret key.
Those *must* be set using the Pulumi CLI using the `--secret` flag:

```console
pulumi config set --secret minio_root_password <your-minio-secret-key>
```

It is critical that you set all required configuration keys before deploying the stack. In particular, you will need to supply a public SSH key that will be added to the SSH server in the access cluster.
If you do not do this, you will not be able to access the isolated cluster later.

For a complete list of configuration keys, see the `Pulumi.yaml` file.

### Kubernetes context

Pulumi requires that the Kubernetes context is set for the stack.
For example, to set the Kubernetes context for the `dawn` stack, you can use:

```console
pulumi config set kubernetes:context dawn
```

This must match one of the contexts in your local `kubeconfig`.
You can check the available contexts with `kubectl`:

```console
kubectl config get-contexts
```

### Deploying with Pulumi

Once you have set up the stack and its configuration, you can deploy the stack using the following command:

```console
pulumi up
```

### Isolated cluster

You will deploy the isolated cluster next, as it hosts the FRIDGE services.
Navigate to the `infra/fridge-dual-cluster/isolated-cluster/` folder.

However, two additional steps are required before deploying FRIDGE to the isolated cluster.

1. **SSH port forwarding**: You must set up SSH port forwarding from your local machine to the isolated cluster via the SSH server in the access cluster.
   This is necessary because the isolated cluster has a private API server endpoint, which is not directly accessible from outside the access cluster.
   You can use the following command to set up SSH port forwarding:

   ```console
   ssh -i <path-to-your-private-ssh-key> -L 6443:<isolated-cluster-api-server>:443 fridgeoperator@<access-cluster-ssh-server-ip> -p 2500 -N
   ```

   Replace `<path-to-your-private-ssh-key>`, `<isolated-cluster-api-server>`, `<ssh-user>`, and `<access-cluster-ssh-server-ip>` with the appropriate values for your setup.
2. **Kubernetes context**: You must set the Kubernetes context for the isolated cluster stack to use the local port forwarded to the isolated cluster's API server.
   Edit the `kubeconfig` file for the isolated cluster to point to `https://localhost:6443` for the API server endpoint.
   Then, set the Kubernetes context for the stack using the Pulumi CLI:

   ```console
   pulumi config set kubernetes:context <isolated-cluster-context>
   ```

Once these steps are complete, you can deploy the isolated cluster stack using the same `pulumi up` command as before, after setting up the virtual environment and creating the stack, and setting the required configuration keys.

## FRIDGE deployment targets

Currently, FRIDGE is configured to support deployment on Azure Kubernetes Service (AKS) and on DAWN AI.
FRIDGE uses Cilium for networking, and thus requires a Kubernetes cluster with Cilium installed.

In the table below, you can see the components need to be deployed to each target.
Some components are pre-installed on DAWN.

| Component         | AKS   | DAWN  | Local |
| ----------------- | ----- | ----- | ----- |
| argo-workflows    | ✅    | ✅    | ✅    |
| cert-manager.io   | ✅    |       | ✅    |
| cilium            |       |       | ✅    |
| fridge-api        | ✅    | ✅    | ✅    |
| harbor            | ✅    | ✅    | ✅    |
| hubble            | ✅    |       | ✅    |
| ingress-nginx     | ✅    |       | ✅    |
| longhorn          |       | ✅    | ✅    |
| minio             | ✅    | ✅    | ✅    |
| prometheus        | ✅    |       | ✅    |
