import base64
import json
import os
import requests
from kubernetes import client, config
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from typing import Annotated


# Load environment variables from .env file
load_dotenv()
FRIDGE_API_ADMIN = os.getenv("FRIDGE_API_ADMIN")
FRIDGE_API_PASSWORD = os.getenv("FRIDGE_API_PASSWORD")

# Check if running in the Kubernetes cluster
# If so, use the in-cluster configuration to retrieve the token
# Note that this requires a service account with the necessary permissions
# If not in the cluster, use the current kube config credentials to retrieve the token
if os.getenv("KUBERNETES_SERVICE_HOST"):
    config.load_incluster_config()
    v1 = client.CoreV1Api()
    secret = v1.read_namespaced_secret(
        "argo-workflows-api-sa.service-account-token", "argo-workflows"
    )
    ARGO_TOKEN = base64.b64decode(secret.data["token"]).decode("utf-8")
    ARGO_SERVER = "argo-server.argo-server.svc.cluster.local:2746"
else:
    ARGO_TOKEN = os.getenv("ARGO_TOKEN")
    ARGO_SERVER = os.getenv("ARGO_SERVER")

description = """
FRIDGE API allows you to interact with the FRIDGE cluster.

## Argo Workflows
You can manage workflows in Argo Workflows using this API.

It provides endpoints to list workflows, get details of a specific workflow,
list workflow templates, get details of a specific workflow template,
and submit workflows based on templates.

"""

app = FastAPI(title="FRIDGE API", description=description, version="0.0.0.999")


security = HTTPBasic()


class Workflow(BaseModel):
    name: str
    namespace: str
    status: str | None = None
    created_at: str | None = None


class WorkflowTemplate(BaseModel):
    namespace: str
    template_name: str
    parameters: list[dict] | None = None


def parse_argo_error(response: dict) -> dict:
    """
    Check for errors in the Argo Workflows response and return those errors if any.
    """

    match response:
        case {"code": 7}:
            return {
                "error": "Namespace not found or not permitted.",
                "argo_status_code": response["code"],
                "message": response["message"],
            }
        case {"code": 5}:
            return {
                "error": "Workflow not found.",
                "argo_status_code": response["code"],
                "response": response["message"],
            }
        case _:
            return {
                "error": "An unknown error occurred.",
                "argo_status_code": response.get("code", 500),
                "message": response.get(
                    "message", "No additional information provided."
                ),
            }


def extract_argo_workflows(response: dict) -> list[Workflow] | Workflow:
    """
    Parse the Argo response to extract workflow information.
    """
    workflows = []
    if "items" in response:
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


def parse_parameters(parameters: list[dict]) -> list[str]:
    """
    Parse the parameters from the workflow template into a list of strings.
    """
    return [
        f"{param['name']}={param['value']}"
        for param in parameters
        if "name" in param and "value" in param
    ]


def verify_request(credentials: HTTPBasicCredentials = Depends(security)):
    """
    Verify the request using basic auth.
    """
    correct_username = FRIDGE_API_ADMIN
    correct_password = FRIDGE_API_PASSWORD

    if (
        credentials.username != correct_username
        or credentials.password != correct_password
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return True


@app.get("/workflows/{namespace}")
async def get_workflows(
    namespace: Annotated[str, "The namespace to list workflows from"],
    verbose: Annotated[
        bool, "Return verbose output - full details of all workflows"
    ] = False,
    verified: Annotated[bool, "Verify the request with basic auth"] = Depends(
        verify_request
    ),
):
    r = requests.get(
        f"{ARGO_SERVER}/api/v1/workflows/{namespace}",
        verify=False,
        headers={"Authorization": f"Bearer {ARGO_TOKEN}"},
    )
    if r.status_code != 200:
        raise HTTPException(
            status_code=r.status_code, detail=parse_argo_error(r.json())
        )
    if verbose:
        return r.json()
    return extract_argo_workflows(r.json())


@app.get("/workflows/{namespace}/{workflow_name}")
async def get_single_workflow(
    namespace: Annotated[str, "The namespace to list workflows from"],
    workflow_name: Annotated[str, "The name of the workflow to retrieve"],
    verbose: Annotated[
        bool, "Return verbose output - full details of the workflow"
    ] = False,
    verified: Annotated[bool, "Verify the request with basic auth"] = Depends(
        verify_request
    ),
):
    r = requests.get(
        f"{ARGO_SERVER}/api/v1/workflows/{namespace}/{workflow_name}",
        verify=False,
        headers={"Authorization": f"Bearer {ARGO_TOKEN}"},
    )
    if r.status_code != 200:
        raise HTTPException(
            status_code=r.status_code, detail=parse_argo_error(r.json())
        )
    if verbose:
        return r.json()
    return extract_argo_workflows(r.json())


@app.get("/workflowtemplates/{namespace}")
async def list_workflow_templates(
    namespace: str,
    verified: Annotated[bool, "Verify the request with basic auth"] = Depends(
        verify_request
    ),
):
    r = requests.get(
        f"{ARGO_SERVER}/api/v1/workflow-templates/{namespace}",
        verify=False,
        headers={"Authorization": f"Bearer {ARGO_TOKEN}"},
    )
    if r.status_code != 200:
        raise HTTPException(
            status_code=r.status_code, detail=parse_argo_error(r.json())
        )
    json_data = r.json()
    return json_data


@app.get("/workflowtemplates/{namespace}/{template_name}")
async def get_workflow_template(
    namespace: str,
    template_name: str,
    verbose: Annotated[
        bool, "Return verbose output - full details of the template"
    ] = False,
    verified: Annotated[bool, "Verify the request with basic auth"] = Depends(
        verify_request
    ),
):
    r = requests.get(
        f"{ARGO_SERVER}/api/v1/workflow-templates/{namespace}/{template_name}",
        verify=False,
        headers={"Authorization": f"Bearer {ARGO_TOKEN}"},
    )
    if r.status_code != 200:
        raise HTTPException(
            status_code=r.status_code, detail=parse_argo_error(r.json())
        )
    json_data = r.json()
    workflow_template = WorkflowTemplate(
        namespace=namespace,
        template_name=template_name,
        parameters=json_data["spec"]["arguments"]["parameters"],
    )
    if verbose:
        return [json_data, workflow_template]
    return workflow_template


@app.post("/workflowevents/from_template/")
async def submit_workflow_from_template(
    workflow_template: WorkflowTemplate,
    verified: Annotated[bool, "Verify the request with basic auth"] = Depends(
        verify_request
    ),
):
    r = requests.post(
        f"{ARGO_SERVER}/api/v1/workflows/{workflow_template.namespace}/submit",
        verify=False,
        headers={"Authorization": f"Bearer {ARGO_TOKEN}"},
        data=json.dumps(
            {
                "resourceKind": "WorkflowTemplate",
                "resourceName": workflow_template.template_name,
                "submitOptions": {
                    "parameters": parse_parameters(workflow_template.parameters)
                    if workflow_template.parameters
                    else []
                },
            }
        ),
    )
    if r.status_code == 403:
        return {
            "error": "Workflow namespace not found or not permitted",
            "status": r.status_code,
            "response": r.text,
        }
    elif r.status_code == 404:
        return {
            "error": "Workflow template not found",
            "status": r.status_code,
            "response": r.text,
        }
    elif r.status_code != 200:
        return {
            "error": "Failed to submit workflow",
            "status": r.status_code,
            "response": r.text,
        }
    return {
        "workflow_submitted": workflow_template,
        "status": r.status_code,
        "response": r.json(),
    }
