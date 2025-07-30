# FRIDGE Job API

This is an API for managing workflows in a FRIDGE cluster.

It is designed to interact with the Argo Workflows API.

## Setup

1. From the root of the project, run `uv sync` to setup the environment and then `uv run fastapi dev app/main.py` to start the API server.
2. The API will be available at `http://localhost:8000`.
3. You can access the OpenAPI documentation at `http://localhost:8000/docs`.

### Local Minio

To run a local minio server for testing, run `make minio-local`. This will expose a minio container on port 9000 with the default credentials as `minioadmin:minioadmin`

## Configuration

The API uses environment variables for configuration. You can set the following variables in a `.env` file:

- `ARGO_SERVER`: The URL of the Argo Workflows server
- `ARGO_TOKEN`: The access token for authenticating with the Argo Workflows server
- `MINIO_URL`: The URL of the Minio server
- `MINIO_ACCESS_KEY`: Access Key to authenticate with Minio server
- `MINIO_SECRET_KEY`: Secret Key to authenticate with the Minio server
- `FRIDGE_API_ADMIN`: The username of the admin user for the FRIDGE API
- `FRIDGE_API_ADMIN_PASSWORD`: The password for the admin user for the FRIDGE API

The access token can be generated and obtained following the instructions in the [Argo Workflows documentation](https://argo-workflows.readthedocs.io/en/latest/access-token/)

In a future version, when deployed on a Kubernetes cluster, the API will automatically retrieve the access token.
