# Deploying a FRIDGE

Deploying a FRIDGE is a multi-stage process.

1. Deploy the networking infrastructure and Kubernetes clusters
1. Deploy FRIDGE services into the access cluster
1. Deploy FRIDGE services into the isolated cluster
1. Perform a final networking lockdown

The Hosting Provider Administrators are responsible for the first and final steps.

The TRE Administrators are responsible for the second and third steps.

For Hosting Provider Administrators, follow the guide in [Deploy Infrastructure](./infrastructure.md)

For TRE Administrators, follow the guide in [Deploy Services](./services.md)

## Prerequisites

You will need the following tools installed to deploy FRIDGE:

- [Python](https://www.python.org/downloads/) 3.11 or later
- [Pulumi](https://www.pulumi.com/docs/get-started/install/)
- [kubectl](https://kubernetes.io/docs/tasks/tools/)

Additionally, if deploying to Azure, you will need the following:

- [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli)

### Pulumi Backend

Pulumi stores state in a backend.
The [Pulumi documentation](https://www.pulumi.com/docs/iac/concepts/state-and-backends/) details how to set up an appropriate backend.
For local development and testing, you can use the local backend:

```console
pulumi login --local
```

For production, another backend, such as Azure Blob Storage, will likely be more appropriate.
