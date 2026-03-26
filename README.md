# FRIDGE: Federated Research Infrastructure by Data Governance Extension

[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://alan-turing-institute.github.io/fridge/)
[![License](https://img.shields.io/badge/license-BSD%203--Clause-blue)](LICENSE)

FRIDGE is a [DARE UK](https://dareuk.org.uk/) Early Adopter project that extends Trusted Research Environments (TREs) to securely leverage the computational resources of the national AI Research Resource (AIRR).
It provides a framework for submitting and managing sensitive data workflows from within a TRE to an external FRIDGE cluster, while enforcing data governance and security policies throughout.
The system is built on Kubernetes for portability across cloud providers and on-premise installations.

## Architecture Overview

At a high level, FRIDGE bridges a TRE and a remote compute cluster:

- A **TRE** submits workflow jobs via the FRIDGE Job API, which translates them into Argo Workflows
- The **FRIDGE cluster** runs those workflows in an isolated environment with access to AIRR compute
- Data governance controls are applied at every boundary

See the [architecture documentation](https://alan-turing-institute.github.io/fridge/architecture/introduction/) for a detailed breakdown including the defence-in-depth model, role definitions, and the job lifecycle.

## Repository Structure

| Directory | Description |
|---|---|
| `fridge-job-api/` | FastAPI service for submitting and managing workflows via the Argo Workflows API |
| `infra/` | Pulumi infrastructure-as-code for supported deployment targets |
| `docs/` | Source for the [project documentation site](https://alan-turing-institute.github.io/fridge/) |

## Prerequisites

- [Python](https://www.python.org/downloads/) 3.11+
- [Pulumi](https://www.pulumi.com/docs/get-started/install/)
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli) *(if deploying to AKS)*

## Deployment

FRIDGE can be deployed to:

- **Azure Kubernetes Service (AKS)** — fully supported, including Pulumi IaC for provisioning the cluster
- **Dawn AI** — fully supported
- **Isambard AI** — under development

See the [deployment documentation](https://alan-turing-institute.github.io/fridge/deploy/prerequisites/) for step-by-step instructions for each target.

## Local Development

To run the `fridge-job-api` locally:

```bash
uv sync
uv run fastapi dev app/main.py
```

The API will be available at `http://localhost:8000`, with OpenAPI docs at `http://localhost:8000/docs`.

See [`fridge-job-api/README.md`](fridge-job-api/README.md) for configuration details, and the [developer documentation](https://alan-turing-institute.github.io/fridge/develop/target/) for broader contributor guidance.

## Contributing

Install [pre-commit](https://pre-commit.com/) and set up the hooks before making changes:

```bash
pip install pre-commit
pre-commit install
```

The hooks run `black` for Python formatting and standard file hygiene checks.

## Documentation

Full documentation is available at **https://alan-turing-institute.github.io/fridge/**

## License

BSD 3-Clause — see [LICENSE](LICENSE) for details.
