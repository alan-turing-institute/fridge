import json
import requests
from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated, Any, Union
from .config import (
    ARGO_SERVER,
    VERIFY_TLS,
    verify_request,
    argo_token,
    Workflow,
    WorkflowTemplate,
    parse_argo_error,
    extract_argo_workflows,
    extract_argo_workflow_templates,
    parse_parameters,
)

router = APIRouter(tags=["Argo Workflows"])


@router.get("/workflows/{namespace}", tags=["Argo Workflows"])
async def get_workflows(
    namespace: Annotated[str, "The namespace to list workflows from"],
    verbose: Annotated[
        bool, "Return verbose output - full details of all workflows"
    ] = False,
    verified: Annotated[bool, "Verify the request with basic auth"] = Depends(
        verify_request
    ),
) -> list[Workflow] | Workflow | dict:
    r = requests.get(
        f"{ARGO_SERVER}/api/v1/workflows/{namespace}",
        verify=VERIFY_TLS,
        headers={"Authorization": f"Bearer {argo_token()}"},
    )
    if r.status_code != 200:
        raise HTTPException(
            status_code=r.status_code, detail=parse_argo_error(r.json())
        )
    if verbose:
        return r.json()
    return extract_argo_workflows(r.json())


@router.get("/workflows/{namespace}/{workflow_name}/log", tags=["Argo Workflows"])
async def get_workflow_log(
    namespace: str,
    workflow_name: str,
    pod_name: str | None = None,
    container_name: str = "main",
    verified: Annotated[bool, "Verify the request with basic auth"] = Depends(
        verify_request
    ),
):
    params = {
        "podName": pod_name or workflow_name,
        "logOptions.container": container_name,
    }

    r = requests.get(
        f"{ARGO_SERVER}/api/v1/workflows/{namespace}/{workflow_name}/log",
        verify=VERIFY_TLS,
        headers={"Authorization": f"Bearer {argo_token()}"},
        params=params,
        stream=True,
    )
    if r.status_code != 200:
        raise HTTPException(
            status_code=r.status_code, detail=parse_argo_error(r.json())
        )

    lines = []
    for line in r.iter_lines():
        if line:
            parsed = json.loads(line)
            if "result" in parsed:
                lines.append(parsed["result"].get("content", ""))
    return {"podName": workflow_name, "log": "\n".join(lines)}


@router.get("/workflows/{namespace}/{workflow_name}", tags=["Argo Workflows"])
async def get_single_workflow(
    namespace: Annotated[str, "The namespace to list workflows from"],
    workflow_name: Annotated[str, "The name of the workflow to retrieve"],
    verbose: Annotated[
        bool, "Return verbose output - full details of the workflow"
    ] = False,
    verified: Annotated[bool, "Verify the request with basic auth"] = Depends(
        verify_request
    ),
) -> list[Workflow] | Workflow | dict:
    r = requests.get(
        f"{ARGO_SERVER}/api/v1/workflows/{namespace}/{workflow_name}",
        verify=VERIFY_TLS,
        headers={"Authorization": f"Bearer {argo_token()}"},
    )
    if r.status_code != 200:
        raise HTTPException(
            status_code=r.status_code, detail=parse_argo_error(r.json())
        )
    if verbose:
        return r.json()
    return extract_argo_workflows(r.json())


@router.get("/workflowtemplates/{namespace}", tags=["Argo Workflows"])
async def list_workflow_templates(
    namespace: str,
    verbose: Annotated[
        bool, "Return verbose output - full details of the templates"
    ] = False,
    verified: Annotated[bool, "Verify the request with basic auth"] = Depends(
        verify_request
    ),
) -> list[WorkflowTemplate] | WorkflowTemplate | dict | Union[list, WorkflowTemplate]:
    r = requests.get(
        f"{ARGO_SERVER}/api/v1/workflow-templates/{namespace}",
        verify=VERIFY_TLS,
        headers={"Authorization": f"Bearer {argo_token()}"},
    )
    if r.status_code != 200:
        raise HTTPException(
            status_code=r.status_code, detail=parse_argo_error(r.json())
        )
    json_data = r.json()
    workflow_templates = extract_argo_workflow_templates(json_data)
    if verbose:
        return [json_data, workflow_templates]
    return workflow_templates


@router.get("/workflowtemplates/{namespace}/{template_name}", tags=["Argo Workflows"])
async def get_workflow_template(
    namespace: str,
    template_name: str,
    verbose: Annotated[
        bool, "Return verbose output - full details of the template"
    ] = False,
    verified: Annotated[bool, "Verify the request with basic auth"] = Depends(
        verify_request
    ),
) -> WorkflowTemplate | dict | Union[Any, WorkflowTemplate]:
    r = requests.get(
        f"{ARGO_SERVER}/api/v1/workflow-templates/{namespace}/{template_name}",
        verify=VERIFY_TLS,
        headers={"Authorization": f"Bearer {argo_token()}"},
    )
    if r.status_code != 200:
        raise HTTPException(
            status_code=r.status_code, detail=parse_argo_error(r.json())
        )
    json_data = r.json()
    workflow_template = WorkflowTemplate(
        namespace=namespace,
        template_name=template_name,
        parameters=json_data.get("spec", {}).get("arguments", {}).get("parameters", []),
    )
    if verbose:
        return [json_data, workflow_template]
    return workflow_template


@router.post("/workflowevents/from_template/", tags=["Argo Workflows"])
async def submit_workflow_from_template(
    workflow_template: WorkflowTemplate,
    verbose: Annotated[
        bool, "Return verbose output - full details of the workflow"
    ] = False,
    verified: Annotated[bool, "Verify the request with basic auth"] = Depends(
        verify_request
    ),
) -> dict:
    r = requests.post(
        f"{ARGO_SERVER}/api/v1/workflows/{workflow_template.namespace}/submit",
        verify=VERIFY_TLS,
        headers={"Authorization": f"Bearer {argo_token()}"},
        data=json.dumps(
            {
                "resourceKind": "WorkflowTemplate",
                "resourceName": workflow_template.template_name,
                "submitOptions": {
                    "parameters": (
                        parse_parameters(workflow_template.parameters)
                        if workflow_template.parameters
                        else []
                    )
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
