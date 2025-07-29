import json
import os
import requests
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from secrets import compare_digest
from typing import Annotated

# Check if running in the Kubernetes cluster
# If so, use the in-cluster configuration to retrieve the token
# Note that this requires a service account with the necessary permissions
# If not in the cluster, use the current kube config credentials to retrieve the token
if os.getenv("KUBERNETES_SERVICE_HOST"):
    FRIDGE_API_ADMIN = os.getenv("FRIDGE_API_ADMIN")
    FRIDGE_API_PASSWORD = os.getenv("FRIDGE_API_PASSWORD")
    ARGO_SERVER = "https://argo-workflows-server.argo-server.svc.cluster.local:2746"
else:
    # Load environment variables from .env file
    load_dotenv()
    FRIDGE_API_ADMIN = os.getenv("FRIDGE_API_ADMIN")
    FRIDGE_API_PASSWORD = os.getenv("FRIDGE_API_PASSWORD")
    ARGO_SERVER = os.getenv("ARGO_SERVER")

description = """
FRIDGE API allows you to interact with the FRIDGE cluster.

## Argo Workflows
You can manage workflows in Argo Workflows using this API.

It provides endpoints to list workflows, get details of a specific workflow,
list workflow templates, get details of a specific workflow template,
and submit workflows based on templates.

"""

app = FastAPI(title="FRIDGE API", description=description, version="0.1.0")


def load_token():
    """
    Load the ARGO token on request from the environment variable or from the service account token file if running in a Kubernetes cluster.
    """
    if os.getenv("KUBERNETES_SERVICE_HOST"):
        with open("/service-account/token", "r") as f:
            ARGO_TOKEN = f.read().strip()
    else:
        ARGO_TOKEN = os.getenv("ARGO_TOKEN")
    return ARGO_TOKEN


ARGO_TOKEN = load_token()

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


@app.get("/workflows/{namespace}", tags=["Argo Workflows"])
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
    print(f"Bearer {ARGO_TOKEN}")
    print(f"{ARGO_SERVER}/api/v1/workflows/{namespace}")
    if r.status_code != 200:
        raise HTTPException(
            status_code=r.status_code, detail=parse_argo_error(r.json())
        )
    if verbose:
        return r.json()
    return extract_argo_workflows(r.json())


@app.get("/workflows/{namespace}/{workflow_name}", tags=["Argo Workflows"])
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


@app.get("/workflowtemplates/{namespace}", tags=["Argo Workflows"])
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


@app.get("/workflowtemplates/{namespace}/{template_name}", tags=["Argo Workflows"])
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


@app.post("/workflowevents/from_template/", tags=["Argo Workflows"])
async def submit_workflow_from_template(
    workflow_template: WorkflowTemplate,
    verbose: Annotated[
        bool, "Return verbose output - full details of the workflow"
    ] = False,
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
    if r.status_code != 200:
        raise HTTPException(
            status_code=r.status_code, detail=parse_argo_error(r.json())
        )
    return {
        "workflow_submitted": workflow_template,
        "status": r.status_code,
        "response": r.json() if verbose else extract_argo_workflows(r.json()),
    }
