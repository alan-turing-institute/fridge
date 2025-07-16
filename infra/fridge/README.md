# FRIDGE deployment instructions

FRIDGE is deployed on Kubernetes using [Pulumi](https://www.pulumi.com/)

## Prerequisites

You will need the following tools installed on your local machine to deploy FRIDGE:

- [Python](https://www.python.org/downloads/) 3.11 or later
- [Pulumi](https://www.pulumi.com/docs/get-started/install/) installed
- [kubectl](https://kubernetes.io/docs/tasks/tools/) installed
- [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli) installed (if using Azure as a backend)

## Pulumi Backend

You can use any backend you like for Pulumi.

The development team use an Azure Storage Account as a backend for Pulumi, and this guide assumes you will do the same.

Begin by a creating a new Pulumi project in a new directory using the `azure-python` template:

```console
pulumi new azure-python
```

Follow the examples in the [Pulumi documentation](https://www.pulumi.com/docs/iac/get-started/azure/create-project/).

To set up the Azure backend, you will need to create a Storage Account and a Container within it.

Then follow the instructions in the [Pulumi documentation](https://www.pulumi.com/docs/iac/concepts/state-and-backends/#azure-blob-storage) to configure your Pulumi project to use the Azure Blob Storage backend.

## Configuring FRIDGE

FRIDGE is configured using a Pulumi configuration file.

## Deploying FRIDGE

Currently, FRIDGE is configured to support deployment on Azure Kubernetes Service (AKS) and on DAWN AI.


|   | AKS | DAWN |
|---|---|---|
| cert-manager.io | | [x] |
| hubble | | [x] |
| ingress-nginx | | [x] |
