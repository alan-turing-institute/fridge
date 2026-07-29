import os
from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from importlib.metadata import PackageNotFoundError, version
from pydantic import BaseModel
from secrets import compare_digest
from app.minio_client import MinioClient

load_dotenv()

if os.getenv("KUBERNETES_SERVICE_HOST"):
    FRIDGE_API_ADMIN = os.getenv("FRIDGE_API_ADMIN")
    FRIDGE_API_PASSWORD = os.getenv("FRIDGE_API_PASSWORD")
    ARGO_SERVER_NS = os.getenv("ARGO_SERVER_NS")
    ARGO_SERVER = (
        f"https://argo-workflows-server.{ARGO_SERVER_NS}.svc.cluster.local.:2746"
    )
else:
    FRIDGE_API_ADMIN = os.getenv("FRIDGE_API_ADMIN")
    FRIDGE_API_PASSWORD = os.getenv("FRIDGE_API_PASSWORD")
    ARGO_SERVER = os.getenv("ARGO_SERVER")

VERIFY_TLS = os.getenv("VERIFY_TLS", "False") == "True"

security = HTTPBasic()


def get_version() -> str:
    """
    Get the version of the application from the package metadata.
    """
    try:
        return version("fridge-job-api")
    except PackageNotFoundError:
        print("Package metadata not found. Returning default version.")
        return "0.0.0-dev"  # Default version if package metadata is not found


# Check if running in the Kubernetes cluster
# If not in the cluster, load environment variables from .env file
if os.getenv("KUBERNETES_SERVICE_HOST"):
    FRIDGE_API_ADMIN = os.getenv("FRIDGE_API_ADMIN")
    FRIDGE_API_PASSWORD = os.getenv("FRIDGE_API_PASSWORD")
    ARGO_SERVER_NS = os.getenv("ARGO_SERVER_NS")
    ARGO_SERVER = (
        f"https://argo-workflows-server.{ARGO_SERVER_NS}.svc.cluster.local.:2746"
    )
    MINIO_CA_BUNDLE = "/etc/ssl/certs/tls-trust-bundle.crt"
else:
    # Load environment variables from .env file
    load_dotenv()
    FRIDGE_API_ADMIN = os.getenv("FRIDGE_API_ADMIN")
    FRIDGE_API_PASSWORD = os.getenv("FRIDGE_API_PASSWORD")
    ARGO_SERVER = os.getenv("ARGO_SERVER")

# Disable TLS verification in development mode
VERIFY_TLS = os.getenv("VERIFY_TLS", "False") == "True"
if not VERIFY_TLS:
    print(
        "Warning: TLS verification is disabled. This is not secure and should only be used in development environments."
    )

# On the Kubernetes cluster, the Argo token is stored in a service account token file on a projected volume
# The token expires after one hour; the file on the volume is updated automatically by Kubernetes
# Reading the token from the file when required ensures that we always use a valid token
# If not running in the cluster, we use the ARGO_TOKEN environment variable
def argo_token() -> str:
    """
    Load the ARGO token on request from the environment variable or from the service account token file if running in a Kubernetes cluster.
    """
    if os.getenv("KUBERNETES_SERVICE_HOST"):
        with open("/service-account/token", "r") as f:
            ARGO_TOKEN = f.read().strip()
    else:
        ARGO_TOKEN = os.getenv("ARGO_TOKEN")
        if ARGO_TOKEN is None:
            raise HTTPException(
                status_code=500,
                detail="ARGO_TOKEN environment variable is not set.",
            )
    return ARGO_TOKEN


# Init minio client. Will fallback to STS if access/secret key are not set
minio_client = MinioClient(
    endpoint=os.getenv("MINIO_URL"),
    sts_endpoint=os.getenv(
        "MINIO_STS_URL", "https://sts.minio-operator.svc.cluster.local.:4223"
    ),
    tenant=os.getenv("MINIO_TENANT_NAME", "argo-artifacts"),
    access_key=os.getenv("MINIO_ACCESS_KEY", None),
    secret_key=os.getenv("MINIO_SECRET_KEY", None),
    secure=os.getenv("MINIO_SECURE", True),
)


class Workflow(BaseModel):
    name: str
    namespace: str
    status: str | None = None
    created_at: str | None = None


class WorkflowTemplate(BaseModel):
    namespace: str
    template_name: str
    parameters: list[dict] | None = None


def parse_argo_error(response: dict) -> dict | None:
    """
    Check for errors in the Argo Workflows response and return those errors if any.
    """

    match response.get("code"):
        case 7:
            return {
                "error": "Namespace not found or not permitted.",
                "argo_status_code": response["code"],
                "message": response["message"],
            }
        case 5:
            if "workflowtemplates" in response["message"]:
                missing_resource = "Workflow template"
            else:
                missing_resource = "Workflow"
            return {
                "error": f"{missing_resource} not found.",
                "argo_status_code": response["code"],
                "response": response["message"],
            }
        case None:
            pass


def extract_argo_workflows(response: dict) -> list[Workflow] | Workflow | dict:
    """
    Parse the Argo response to extract workflow information.
    """
    workflows = []
    if "items" in response:
        if not response["items"]:
            return {"message": "No workflows found in the specified namespace."}
        for item in response["items"]:
            workflow = Workflow(
                name=item.get("metadata", {}).get("name"),
                namespace=item.get("metadata", {}).get("namespace"),
                status=item.get("status", {}).get("phase"),
                created_at=item.get("metadata", {}).get("creationTimestamp"),
            )
            workflows.append(workflow)
        return workflows
    else:
        workflow = Workflow(
            name=response.get("metadata", {}).get("name"),
            namespace=response.get("metadata", {}).get("namespace"),
            status=response.get("status", {}).get("phase"),
            created_at=response.get("metadata", {}).get("creationTimestamp"),
        )
        return workflow


def extract_argo_workflow_templates(
    response: dict,
) -> list[WorkflowTemplate] | WorkflowTemplate | dict:
    """
    Parse the Argo response to extract workflow information.
    """
    workflows = []
    if "items" in response:
        if not response["items"]:
            return {"message": "No workflows found in the specified namespace."}
        for item in response["items"]:
            workflow = WorkflowTemplate(
                template_name=item.get("metadata", {}).get("name"),
                namespace=item.get("metadata", {}).get("namespace"),
                parameters=item.get("spec", {})
                .get("arguments", {})
                .get("parameters", []),
            )
            workflows.append(workflow)
        return workflows
    else:
        workflow = WorkflowTemplate(
            template_name=response.get("metadata", {}).get("name"),
            namespace=response.get("metadata", {}).get("namespace"),
            parameters=response.get("spec", {})
            .get("arguments", {})
            .get("parameters", []),
        )
        return workflow


def parse_parameters(parameters: list[dict]) -> list[str]:
    """
    Parse the parameters from the workflow template into a list of strings.
    """
    return [
        f"{param['name']}={param['value']}"
        for param in parameters
        if "name" in param and "value" in param
    ]


def verify_request(credentials: HTTPBasicCredentials = Depends(security)) -> bool:
    """
    Verify the request using basic auth.
    """
    correct_username = bytes(FRIDGE_API_ADMIN, "utf-8")
    correct_password = bytes(FRIDGE_API_PASSWORD, "utf-8")
    current_username = credentials.username.encode("utf-8")
    current_password = credentials.password.encode("utf-8")

    if not (
        compare_digest(current_username, correct_username)
        and compare_digest(current_password, correct_password)
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return True
