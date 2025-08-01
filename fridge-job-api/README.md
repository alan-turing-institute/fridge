# FRIDGE Job API

This is an API for managing workflows in a FRIDGE cluster.

It is designed to interact with the Argo Workflows API.

## Local deployment

### Setup

1. From the root of the project, run `uv sync` to setup the environment and then `uv run fastapi dev main.py` to start the API server.
2. The API will be available at `http://localhost:8000`.
3. You can access the OpenAPI documentation at `http://localhost:8000/docs`.
4. The API requires basic HTTP authentication. You can use the `FRIDGE_API_ADMIN` and `FRIDGE_API_PASSWORD` environment variables to authenticate.

### Configuration

The API uses environment variables for configuration. You can set the following variables in a `.env` file:

- `ARGO_SERVER`: The URL of the Argo Workflows server
- `ARGO_TOKEN`: The access token for authenticating with the Argo Workflows server
- `FRIDGE_API_ADMIN`: The username of the admin user for the FRIDGE API
- `FRIDGE_API_PASSWORD`: The password for the admin user for the FRIDGE API

An appropriate access token can be generated and obtained following the instructions in the [Argo Workflows documentation](https://argo-workflows.readthedocs.io/en/latest/access-token/)

## Remote deployment

When deploying the API on a Kubernetes cluster, the access token is automatically retrieved from the service account token mounted at `/service-account/token`.

The API will use this token to authenticate with the Argo Workflows server.

## Configuration for Pulumi

When configuring the Pulumi stack, some values need to be set as secrets. Use the following commands to set them:

```bash
pulumi config set --secret fridge_api_admin <your_fridge_api_admin>
pulumi config set --secret fridge_api_password <your_fridge_api_password>
```
