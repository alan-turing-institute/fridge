import os
import requests
from dotenv import load_dotenv
from fastapi import FastAPI
from typing import Annotated

app = FastAPI()

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
        f"https://argo.dawn.fridge.develop.turingsafehaven.ac.uk/api/v1/workflow-templates/{namespace}",
        verify=False,
        headers={"Authorization": f"Bearer {ARGO_TOKEN}"},
    )
    json_data = r.json()
    return json_data


@app.get("/workflowtemplates/{namespace}/{template_name}")
async def get_workflow_template(namespace: str, template_name: str):
    r = requests.get(
        f"https://argo.dawn.fridge.develop.turingsafehaven.ac.uk/api/v1/workflow-templates/{namespace}/{template_name}",
        verify=False,
        headers={"Authorization": f"Bearer {ARGO_TOKEN}"},
    )
    json_data = r.json()
    return json_data
