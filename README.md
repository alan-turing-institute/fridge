# FRIDGE: Federated Research Infrastructure by Data Governance Extension

[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://alan-turing-institute.github.io/fridge/)
[![License](https://img.shields.io/badge/license-BSD%203--Clause-blue)](LICENSE)

FRIDGE is a [DARE UK](https://dareuk.org.uk/) Early Adopter project that extends Trusted Research Environments (TREs) to securely leverage the computational resources of the national AI Research Resource (AIRR).
It provides a framework for submitting and managing sensitive data workflows from within a TRE to an external FRIDGE cluster, while enforcing data governance and security policies throughout.
The system is built on Kubernetes for portability across cloud providers and on-premise installations.

## Documentation

Full documentation is available at **https://alan-turing-institute.github.io/fridge/**

## Repository Structure

| Directory | Description |
|---|---|
| `fridge-job-api/` | FastAPI service for submitting and managing workflows, and passing data between the FRIDGE and TRE |
| `infra/` | Pulumi infrastructure-as-code for supported deployment targets |
| `docs/` | Source for the [project documentation site](https://alan-turing-institute.github.io/fridge/) |
