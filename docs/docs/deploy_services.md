# Deploy Services

This page explains how to deploy the FRIDGE services to a Kubernetes cluster.
This process includes configuring for various components such as Argo Workflows, MinIO, network policies, and other infrastructure settings.
It does not deploy the Kubernetes cluster itself; instead, it assumes that a Kubernetes cluster is already available.

To read about deploying the Kubernetes cluster see [Deploy Infrastructure](deploy_infrastructure.md).

Note that container-based Kubernetes environments such as K3d or Kind are not supported, as Longhorn is not compatible with those environments.

## Deployment

### Pulumi Backend

You can use any backend you like for Pulumi.
The [Pulumi documentation](https://www.pulumi.com/docs/iac/concepts/state-and-backends/) details how to use various backends.
For local development and testing, you can use the local backend:

```console
pulumi login --local
```

### Virtual Environment

First, set up a virtual environment for this project.
You can use the following commands:

```console
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Creating a stack

The `infra/fridge/` folder already contains a Pulumi project configuration file (`Pulumi.yaml`), so you do not need to run `pulumi new` to create a new project.
The `Pulumi.yaml` file defines the project name and a schema for the configurations for individual stacks.

To create a new stack, you can use the following command:

```console
pulumi stack init <stack-name>
```

Note: you will be asked to provide a passphrase for the stack, which is used to encrypt secrets within the stack's configuration settings.

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
