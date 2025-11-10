# Deploy Infrastructure

!!! note
    To read about deploying the services on top of the Kubernetes cluster see [Deploy Services](./services.md).

This page explains how to deploy the Kubernetes cluster for FRIDGE using Pulumi, and how to lock it down after deployment of the FRIDGE services.

## Azure Kubernetes Service (AKS)

The FRIDGE infrastructure can be deployed to Azure using Azure Kubernetes Service (AKS).

An example Pulumi project for deploying FRIDGE to AKS is available in the `fridge/infra/fridge-aks/` folder.

This project deploys two AKS clusters: an access cluster, which will host the Harbor container registry and an SSH server for accessing the isolated cluster; and an isolated cluster, which will host the FRIDGE services.

The access cluster has a public API server endpoint, while the isolated cluster has a private API server endpoint, accessible only from within the access cluster.

The example project also deploys the necessary networking components, such as virtual networks, subnets, and network security groups, to ensure secure communication between the clusters.

You will need to supply a public SSH key for accessing the SSH server in the access cluster.

To deploy the infrastructure, follow these steps:

1. Set up a virtual environment for the project:

    ```console
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

2. Create a new Pulumi stack:

    ```console
    pulumi stack init <stack-name>
    ```

3. Configure the stack with the necessary settings, such as the Azure region, resource group name, and SSH public key:

    ```console
    pulumi config set azure:location <region>
    pulumi config set resource_group_name <resource-group-name>
    pulumi config set ssh_public_key "<your-ssh-public-key>"
    ```

4. Deploy the infrastructure:

    ```console
    pulumi up
    ```
