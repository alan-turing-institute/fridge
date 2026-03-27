# Deploy Services

This page explains how to deploy the FRIDGE services to a FRIDGE tenancy.
This process includes configuration for various components such as Argo Workflows, MinIO, network policies, and other infrastructure settings.
It does not deploy the Kubernetes clusters within the FRIDGE tenancy; instead, it assumes that Kubernetes clusters have already been deployed.

:::{seealso}
To read about deploying the required Kubernetes clusters see [Deploy Infrastructure](./infrastructure.md).
:::

:::{warning}
Container-based Kubernetes environments such as K3d or Kind are not supported, as Longhorn is not compatible with those environments.
:::

## Deployment

A FRIDGE consists of two Kubernetes clusters: an access cluster and an isolated cluster.
The access cluster hosts the Harbor container registry and an SSH server for accessing the isolated cluster.
The isolated cluster hosts the FRIDGE services.

The deployment process uses Pulumi to manage the infrastructure as code.

Currently, FRIDGE is configured to support deployment on Azure Kubernetes Service (AKS) and on DAWN AI.
The isolated cluster can be deployed to a local k3s instance.

In the table below, you can see the components that need to be deployed to each target after cluster creation.
Some components are pre-installed on AKS and DAWN.

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


You will require appropriate Kubernetes contexts set up for both clusters.
The FRIDGE hosting organisation should provide you with the required Kubernetes credentials.

:::{note}
The following instructions assume you already have access to Kubernetes clusters deployed in accordance with the instructions in [Deploy Infrastructure](./infrastructure.md).
:::

### Pulumi Backend

You can use any backend you like for Pulumi.
The [Pulumi documentation](https://www.pulumi.com/docs/iac/concepts/state-and-backends/) details how to use set up an appropriate backend.
For local development and testing, you can use the local backend:

```console
pulumi login --local
```

For production, another backend, such as Azure Blob Storage, will be more appropriate.

### Access cluster

You will deploy the access cluster first, as it hosts the Harbor container registry and SSH server required to access the isolated cluster.
Navigate to the `infra/fridge/access-cluster/` folder.

#### Create a stack

The `infra/fridge/access-cluster/` folder already contains a Pulumi project configuration file (`Pulumi.yaml`), so you do not need to run `pulumi new` to create a new project.
The `Pulumi.yaml` file defines the project name and a schema for the configurations for individual stacks.

To create a new stack, you can use the following command:

```console
pulumi stack init <stack-name>
```

:::{note}
You will be asked to provide a passphrase for the stack, which is used to encrypt secrets within the stack's configuration settings.
:::

#### Configure the stack

Each stack has its own configuration settings, defined in the `Pulumi.<stack-name>.yaml` files.
The configuration can be manually edited, or you can use the Pulumi CLI to set configuration values.
You can set individual configuration values for the stack using the following command:

```console
pulumi config set <key> <value>
```

Some of the configuration keys must be set as secrets, such as the `MinIO` access key and secret key.
Those *must* be set using the Pulumi CLI using the `--secret` flag:

```console
pulumi config set --secret minio_root_password <your-minio-secret-key>
```

It is critical that you set all required configuration keys before deploying the stack.
In particular, you will need to supply public SSH keys that will be added to the SSH servers in the access cluster.
If you do not do this, you will not be able to access the isolated cluster later.

For a complete list of configuration keys, see the `Pulumi.yaml` file.

:::{important}
You will need to provide *two* public SSH keys.
One will be copied to the FRIDGE API proxy, and can be used to set up the SSH tunnel to the FRIDGE API.
The other will be copied to the K8s API proxy, and can be used to set up the SSH tunnel to the Kubernetes API of the isolated cluster.
:::

#### Kubernetes context

Pulumi requires that the Kubernetes context is set for the stack.
For example, to set the Kubernetes context for the `dawn` stack, you can use:

```console
pulumi config set kubernetes:context dawn
```

This must match one of the Kubernetes contexts in your local `kubeconfig`.
You can check the available contexts with `kubectl`:

```console
kubectl config get-contexts
```

#### Deploying with Pulumi

Once you have set up the stack and its configuration, you can deploy the stack using the following command:

```console
pulumi up
```

### Isolated cluster

You will deploy the isolated cluster next, as it hosts the FRIDGE services.
Navigate to the `infra/fridge/isolated-cluster/` folder.

However, two additional steps are required before deploying FRIDGE to the isolated cluster.

1. **SSH port forwarding**: You must set up SSH port forwarding from your deployment machine to the isolated cluster via the SSH server in the access cluster.
   The isolated cluster has a private API server endpoint, which is not directly accessible from outside the access cluster.
   You can use the following command to set up SSH port forwarding:

   ```console
   ssh -i <path-to-your-private-ssh-key> -L 6443:<isolated-cluster-api-server>:443 fridgeoperator@<access-cluster-ssh-server-ip> -p 2800 -N
   ```

   Replace `<path-to-your-private-ssh-key>`, `<isolated-cluster-api-server>`, and `<access-cluster-ssh-server-ip>` with the appropriate values for your setup.
2. **Kubernetes context**: You must set the Kubernetes context for the isolated cluster stack to use the local port forwarded to the isolated cluster's API server.
   Edit the `kubeconfig` file for the isolated cluster to point to `https://localhost:6443` for the API server endpoint.
   Then, set the Kubernetes context for the stack using the Pulumi CLI:

   ```console
   pulumi config set kubernetes:context <isolated-cluster-context>
   ```

:::{note}
You may have to use different ports locally if the port suggested above (6443) is in use.
:::

Once these steps are complete, you can deploy the isolated cluster stack using the same `pulumi up` command as before, after creating the stack, and setting the required configuration keys.
