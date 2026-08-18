from fastapi import FastAPI
from .config import get_version
from .storage import router as storage_router
from .workflows import router as workflows_router

APP_VERSION = get_version()

description = """
FRIDGE API allows you to interact with the FRIDGE cluster.

## Argo Workflows
You can manage workflows in Argo Workflows using this API.

It provides endpoints to list workflows, get details of a specific workflow,
list workflow templates, get details of a specific workflow template,
and submit workflows based on templates.

"""

app = FastAPI(title="FRIDGE API", description=description, version=APP_VERSION)

app.include_router(workflows_router)
app.include_router(storage_router)
