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

# Prerequisites

You will need the following tools installed to deploy FRIDGE:

- [Python](https://www.python.org/downloads/) 3.11 or later
- [Pulumi](https://www.pulumi.com/docs/get-started/install/)
- [kubectl](https://kubernetes.io/docs/tasks/tools/)

Additionally, if deploying to Azure, you will need the following:

- [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli)

We also *highly* recommend the [k9s](https://k9scli.io) tool for working with your Kubernetes clusters.
