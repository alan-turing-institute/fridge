# Deploy Services

This page explains how to deploy the FRIDGE services to a FRIDGE tenancy.
This process includes configuration for various components such as Argo Workflows, MinIO, network policies, and other infrastructure settings.
It does not deploy the Kubernetes clusters within the FRIDGE tenancy; instead, it assumes that Kubernetes clusters have already been deployed.

:::{seealso}
To read about deploying the required Kubernetes clusters and tenancy see [Deploy Infrastructure](./infrastructure.md).
:::

:::{warning}
Container-based Kubernetes environments such as `k3d` or `Kind` are not supported, as `Longhorn` is not compatible with those environments.
:::

## Deployment

A FRIDGE consists of two Kubernetes clusters: an `access cluster` and an `isolated cluster`.
The access cluster hosts the `Harbor` container registry and the VPN agent ([NetBird](https://netbird.io)) by which connections to the FRIDGE can be made.
The isolated cluster hosts the FRIDGE services.

The deployment process uses Pulumi to manage the infrastructure as code.

Currently, FRIDGE is configured to support deployment on Azure Kubernetes Service (AKS) and on DAWN.
The isolated cluster can also be deployed to a local [k3s](https://k3s.io/) instance.

You will require appropriate Kubernetes contexts for both clusters.
The `Hosting Organisation` should provide you with the required credentials.

:::{note}
The following instructions assume you already have access to Kubernetes clusters deployed in accordance with the instructions in [Deploy Infrastructure](./infrastructure.md).
It also assumes that you have set up an appropriate [Pulumi backend](./overview.md#pulumi-backend)
:::

### Access cluster

You will deploy the access cluster first, as it hosts the Harbor container registry and VPN agent required to access and subsequently deploy services into the isolated cluster.
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
Those *must* be set using the Pulumi CLI using the `--secret` flag.
For example, the following command sets the `minio_root_password`:

```console
pulumi config set --secret minio_root_password <your-minio-secret-key>
```

It is critical that you set all required configuration keys before deploying the stack.
In particular, you will need to supply a setup up key for NetBird.
The setup key will be used to register the NetBird agent in the cluster with the VPN mesh overlay network.
For a guide to configuring NetBird, see the [Configuring NetBird](./netbird.md) documentation.

For a complete list of configuration keys, see the `Pulumi.yaml` file.

#### Kubernetes context

Pulumi requires that the Kubernetes context is set for the stack.
This must match one of the Kubernetes contexts in your local `kubeconfig`.
You can check the available contexts with `kubectl`:

```console
kubectl config get-contexts
```

For example, to set the Kubernetes context for the `dawn` stack, you can use:

```console
pulumi config set kubernetes:context dawn
```

#### Deploying with Pulumi

Ensure that you are able to connect to the Kubernetes API of the access cluster.

On AKS, the Kubernetes API is publicly accessible during development/testing, so no changes to your local `kubeconfig` are required.

On Dawn, you will need to set up an SSH connection to the bastion host on the access cluster's local network.

Once you have set up the stack and its configuration, you can deploy the stack using the following command:

```console
pulumi up
```

### Isolated cluster

You will deploy the isolated cluster next, as it hosts the FRIDGE services.
Navigate to the `infra/fridge/isolated-cluster/` folder.

Two additional steps are required before deploying FRIDGE to the isolated cluster.

1. **VPN access**: You must run the deployment steps from a machine connected to the VPN mesh overlay network.
   The connecting machine must be part of a NetBird Group that has permission to communicate with the NetBird agent in the access cluster on TCP port 6443
2. **Kubernetes context**: You must modify the Kubernetes context for the isolated cluster stack to use the local port forwarded to the isolated cluster's API server.
   We recommend that you make a dedicated copy of the `kubeconfig` file for the isolated cluster. Edit it to point to `https://<netbird-fqdn-or-ip>:6443`, as per the [NetBird instructions](./netbird.md#connecting-over-the-vpn)
   Then, set the Kubernetes context for the stack using the Pulumi CLI:

   ```console
   pulumi config set kubernetes:context <isolated-cluster-context>
   ```

:::{important}
You must be connected to the VPN mesh overlay network to communicate with the Kubernetes API of the isolated cluster
:::

Once the stack is configured and you have verified that you can connect to the isolated cluster's Kubernetes API, you can deploy the isolated cluster stack using `pulumi up`.

Note that `pulumi up` can safely be repeated if any errors arise.
Sometimes errors during deployment are due to race conditions that Pulumi cannot mitigate, and a repeated attempt will be successful.
