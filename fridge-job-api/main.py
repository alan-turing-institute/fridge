import json
import os
import requests
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Annotated


class WorkflowTemplate(BaseModel):
    namespace: str
    template_name: str
    parameters: list[dict] | None = None


app = FastAPI()


def parse_parameters(parameters: list[dict]) -> list[str]:
    """
    Parse the parameters from the workflow template into a list of strings.
    """
    return [
        f"{param['name']}={param['value']}"
        for param in parameters
        if "name" in param and "value" in param
    ]


# Load environment variables from .env file
load_dotenv()
ARGO_TOKEN = os.getenv("ARGO_TOKEN")
ARGO_SERVER = os.getenv("ARGO_SERVER")
if not ARGO_TOKEN or not ARGO_SERVER:
    raise ValueError(
        "ARGO_TOKEN and ARGO_SERVER must be set in the environment variables."
    )


@app.get("/workflows/{namespace}")
async def get_workflows(
    namespace: Annotated[str, "The namespace to list workflows from"]
):
    r = requests.get(
        f"{ARGO_SERVER}/api/v1/workflows/{namespace}",
        verify=False,
        headers={"Authorization": f"Bearer {ARGO_TOKEN}"},
    )

    return r.json()


@app.get("/workflows/{namespace}/{workflow_name}")
async def get_single_workflow(
    namespace: Annotated[str, "The namespace to list workflows from"],
    workflow_name: Annotated[str, "The name of the workflow to retrieve"],
):
    r = requests.get(
        f"{ARGO_SERVER}/api/v1/workflows/{namespace}/{workflow_name}",
        verify=False,
        headers={"Authorization": f"Bearer {ARGO_TOKEN}"},
    )
    return r.json()


@app.get("/workflowtemplates/{namespace}")
async def list_workflow_templates(namespace: str):
    r = requests.get(
        f"{ARGO_SERVER}/api/v1/workflow-templates/{namespace}",
        verify=False,
        headers={"Authorization": f"Bearer {ARGO_TOKEN}"},
    )
    json_data = r.json()
    return json_data


@app.get("/workflowtemplates/{namespace}/{template_name}")
async def get_workflow_template(namespace: str, template_name: str):
    r = requests.get(
        f"{ARGO_SERVER}/api/v1/workflow-templates/{namespace}/{template_name}",
        verify=False,
        headers={"Authorization": f"Bearer {ARGO_TOKEN}"},
    )
    json_data = r.json()
    workflow_template = WorkflowTemplate(
        namespace=namespace,
        template_name=template_name,
        parameters=json_data["spec"]["arguments"]["parameters"],
    )
    return [json_data, workflow_template]


@app.post("/workflowevents/from_template/")
async def submit_workflow_from_template(workflow_template: WorkflowTemplate):
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
    return {
        "workflow_submitted": workflow_template,
        "status": r.status_code,
        "response": r.json(),
    }
