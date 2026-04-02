---
short_title: Role Catalogue
---
(arch-roles)=
# Role Catalogue

This page explains the responsibilities of each role within a FRIDGE deployment, covering both the overall governance and shared responsibility architecture and the operational processes across the FRIDGE lifecycle.

## Role Summary

:::{glossary}
TRE Operator Organisation
: Operates the {term}`Home TRE` and the FRIDGE {term}`Satellite TRE`, manages technical security controls, and may receive delegated approval authority from the {term}`Data Owner`.
  See [details](#role-tre-operator-organisation).

FRIDGE Hosting Organisation
: Provisions and secures resources on the FRIDGE hosting facility to host the {term}`Satellite TRE`.
  See [details](#role-fridge-hosting-organisation).

Resource Allocator
: Approves compute resource requests and monitors resource utilisation of the platform hosting FRIDGE.
  See [details](#role-resource-allocator).

FRIDGE Federation Governance
: Accountable for risk, determining requirements, and monitoring performance.
  See [details](#role-fridge-federation-governance) and [FRIDGE Governance](shared_gov_model.md).

Operational Management Group
: Representatives from the technical groups running FRIDGE, information governance experts, and researchers as appropriate to manage risk in day-to-day operations.
  See [details](#role-operational-management-group) and [FRIDGE Governance](shared_gov_model.md).

Information Governance Team
: The team within the {term}`TRE Operator Organisation` responsible for information governance and compliance.
  See [details](#role-information-governance-team).

TRE Administrator
: Deploys FRIDGE components under responsibility of {term}`TRE Operator Organisation` (blue in the diagrams).
  See [details](#role-tre-administrator).

Hosting Administrator
: Deploys FRIDGE components under responsibility of {term}`FRIDGE Hosting Organisation` (green in the diagrams).
  See [details](#role-hosting-administrator).

Principal Investigator
: Leads research projects, submits Safe Project applications, and nominates researchers.
  See [details](#role-principal-investigator).

Safe Researcher
: Researcher who has completed training, signed attestation, and been approved for data access.
  Authorised to use the TRE. See [details](#role-safe-researcher).

Job Submitter
: A subset of {term}`Safe Researcher` who can submit FRIDGE jobs (that is dispatch jobs to a remote resource).
  See [details](#role-job-submitter).

Data Owner
: The organisation or individual that owns the sensitive data used in the research project.
  See [details](#role-data-owner).
:::


## Organisational Roles

(role-tre-operator-organisation)=
### TRE Operator Organisation

The organisation that runs the {term}`Trusted Research Environment` used by researchers — the "front door" through which researchers access sensitive data.
This is typically a university, research institution or data provider that operates a TRE.
The {term}`TRE Operator Organisation` is accountable for researcher accreditation, data governance within the TRE, and the security of the research environment built on top of the FRIDGE infrastructure.

#### Governance and architecture responsibilities

- Operates the full stack TRE (the "front door" TRE) and the FRIDGE ({term}`Satellite TRE`).
- Manages technical security controls within the TRE ("front door" and "satellite").
- Assumes responsibility for the TRE platform and code ("front door" and "satellite"), identity and access management, encryption, output management, and researcher accreditation.
- May receive delegated approval authority from the {term}`Data Owner`.

#### Lifecycle process responsibilities

- Receives allocation details from the {term}`FRIDGE Hosting Organisation` and passes them to the {term}`Principal Investigator`.
- Instructs {term}`TRE Administrator` to deploy or decommission the TRE and FRIDGE instance.
- Acts as the coordination point between governance, technical teams, and researchers throughout the lifecycle.
- Receives teardown and data deletion confirmation from the {term}`FRIDGE Hosting Organisation` and passes this to the {term}`Principal Investigator`.


(role-fridge-hosting-organisation)=
### FRIDGE Hosting Organisation

The organisation that owns and operates the supercomputing infrastructure on which FRIDGE runs.
This is likely to be a national compute facility such as [AIRR](https://www.gov.uk/government/publications/ai-research-resource).
This role could also be fulfilled by a public cloud provider or a private cloud hosted by another institution.

#### Governance and architecture responsibilities

- Operates, manages and controls the physical hardware, network infrastructure, tenancy isolation, and Kubernetes cluster management.
- Acts as owner for the underlying infrastructure on which the FRIDGE {term}`Satellite TRE` runs.
- Represented on the {term}`Operational Management Group`.

#### Lifecycle process responsibilities

- Receives requests from the {term}`TRE Operator Organisation` and provisions FRIDGE resource allocations and provides accounts for the {term}`TRE Administrator`.
- Deploys and tears down the Access Cluster and Isolated Cluster on request from {term}`TRE Administrator`.
- Applies lockdown configurations to clusters once instructed by {term}`TRE Administrator`.
- Provides connection details to {term}`TRE Administrator` following deployment.
- Confirms teardown completion and provides data deletion assurance to the {term}`TRE Operator Organisation` at project termination.
- Closes the FRIDGE allocation at project end.

(role-resource-allocator)=
### Resource Allocator

Responsible for managing access to the supercomputing platform.
This role controls who can use the platform and how much compute resource they are allocated.
On national infrastructure this is likely to be a national body appointed by government.
For public cloud the resource allocator will be the bill payer.

#### Governance and architecture responsibilities

- Approves compute resource requests for the supercomputing platform hosting FRIDGE.
- Monitors resource utilisation of the platform.
- Retains responsibility for ensuring that projects and their associated workspace resource allocations are appropriate and justified.

## Governance Roles

(role-fridge-federation-governance)=
### FRIDGE Federation Governance

The strategic governance body for the FRIDGE federation, bringing together senior representatives from the {term}`TRE Operator Organisation`, {term}`FRIDGE Hosting Organisation`, and the {term}`Resource Allocator` and provides the accountability and oversight layer that sits above day-to-day operations.
It also incorporates a PPIE function to ensure public and patient perspectives are reflected in how sensitive data research is conducted.

#### Governance and architecture responsibilities

- Accountable for risk, determining requirements, and monitoring performance.
- Receives requirements from data providers and sets requirements that flow to the {term}`Operational Management Group`.
- Receives risk and performance monitoring reports from the {term}`Operational Management Group`.
- Incorporates the {term}`Resource Allocator`, a PPIE function, and {term}`Operational Management Group` representation.

(role-operational-management-group)=
### Operational Management Group

A cross-organisational working group made up of representatives from the technical, governance, and research teams involved in operating FRIDGE.
A standing group that brings together the parties who need to coordinate to keep the platform running safely.
Membership includes the {term}`Information Governance Team`, the {term}`Hosting Administrator`, the {term}`TRE Administrator`, and researcher representatives as appropriate.

#### Governance and architecture responsibilities

- Responsible for the day-to-day operation of the overall FRIDGE.
- Manages risk within defined tolerances and escalates to {term}`FRIDGE Federation Governance` where necessary.
- Monitors shared cross-organisation processes, ensuring handoffs between parties are evidenced and reported.
- Reports risk and performance information to {term}`FRIDGE Federation Governance`.
- Comprises the {term}`Information Governance Team`, {term}`Hosting Administrator`, {term}`TRE Administrator`, and {term}`Principal Investigators <Principal Investigator>` or {term}`Safe Researchers <Safe Researcher>` as appropriate.

(role-information-governance-team)=
### Information Governance Team

The team within the {term}`TRE Operator Organisation` responsible for information governance.

#### Governance and architecture responsibilities

- Maintains compliance with legislation and external standards.
- Provides expertise and liaison between governance tiers and research teams.
- Acts as the primary IG contact for external parties and as an escalation point for IG matters.
- Represented on the {term}`Operational Management Group`.

## Technical Roles

(role-tre-administrator)=
### TRE Administrator

A technical team within the {term}`TRE Operator Organisation` with hands-on responsibility for deploying and maintaining the TRE and its FRIDGE components.
Typically research computing or platform engineers who understand both the security requirements of TRE operation and the technical implementation of the FRIDGE architecture, including Kubernetes, {term}`Satellite TRE` deployment, and the connection between the TRE and FRIDGE clusters.

#### Governance and architecture responsibilities

- Deploys FRIDGE components under the responsibility of the {term}`TRE Operator Organisation`.
- Responsible for the technical operation and maintenance of the {term}`Trusted Research Environment`.
- Accountable for maintaining technical security controls within the TRE.

#### Lifecycle process responsibilities

- Deploys the TRE on instruction from the {term}`TRE Operator Organisation`.
- Requests FRIDGE deployment from {term}`Hosting Administrator`, providing configuration requirements.
- Requests lockdown from {term}`Hosting Administrator` and confirms lockdown is complete before reporting back to the {term}`TRE Operator Organisation`.
- Initiates TRE disconnection from FRIDGE at teardown.
- Requests FRIDGE teardown from {term}`Hosting Administrator`.

(role-hosting-administrator)=
### Hosting Administrator

A technical team from the {term}`FRIDGE Hosting Organisation` with hands-on responsibility for the underlying supercomputing infrastructure.
Operates at the infrastructure layer — managing physical or virtual hardware, network isolation, and cluster provisioning with no access to the TRE itself.
They act on instructions from the {term}`TRE Administrator` but operate within the security boundary and policies of the {term}`FRIDGE Hosting Organisation`.

#### Governance and architecture responsibilities

- Deploys FRIDGE components under the responsibility of the {term}`FRIDGE Hosting Organisation`.
- Accountable for the safe operation of the underlying infrastructure supporting the {term}`Satellite TRE`.
- Represented on the {term}`Operational Management Group`.

#### Process responsibilities

- Deploys the Access Cluster and Isolated Cluster on request from {term}`TRE Administrator`.
- Provides connection details to {term}`TRE Administrator` following deployment.
- Applies network and cluster lockdown configurations on instruction from {term}`TRE Administrator`.
- Confirms lockdown completion.
- Tears down the Access Cluster and Isolated Cluster at project end.

## Researcher Roles

(role-principal-investigator)=
### Principal Investigator

The academic or research lead responsible for a specific research project using FRIDGE.
They are the named individual accountable for how sensitive data is used within their project.

#### Governance and architecture responsibilities

- Leads research projects and submits Safe Project applications.
- Nominates {term}`Safe Researchers <Safe Researcher>` for data access.
- Accountable for the safe use of data within the project.

#### Process responsibilities

- Obtains approval from the {term}`Data Owner` to use sensitive data prior to project initiation.
- Requests a TRE workspace with FRIDGE from the {term}`TRE Operator Organisation`.
- Receives allocation details and TRE connection details from the {term}`TRE Operator Organisation`.
- Uploads sensitive input data to immutable storage.
- Requests FRIDGE instance teardown when research is complete.
- Receives and passes on data deletion confirmation to the {term}`Data Owner` at project termination.

(role-safe-researcher)=
### Safe Researcher

A researcher who has been formally accredited to access sensitive data within the TRE.
{term}`Safe Researchers <Safe Researcher>` work within the TRE but do not directly interact with the FRIDGE infrastructure.

#### Governance and architecture responsibilities

- Has completed required information governance training, signed the approved researcher agreement, and been approved for data access.
- Authorised to use the TRE within the boundaries of the approved project.

#### Process responsibilities

- Works within the TRE to identify research questions for FRIDGE.

(role-job-submitter)=
### Job Submitter

A {term}`Safe Researcher` who has been granted additional permissions to interact directly with the FRIDGE API — submitting compute jobs, managing container images, and retrieving results.
Not all {term}`Safe Researchers <Safe Researcher>` will need or hold this role; it is assigned to those members of the research team who are responsible for the computational aspects of the project, such as running AI models or large-scale data processing workloads on the supercomputer.

#### Governance and architecture responsibilities

- A subset of the {term}`Safe Researcher` role with additional authorisation to dispatch jobs to the FRIDGE remote resource.

#### Process responsibilities

- Pushes custom container images to the FRIDGE API.
- Submits job specifications to the FRIDGE API.
- Monitors job status and downloads results from the FRIDGE API.

## External Roles

(role-data-owner)=
### Data Owner

The organisation or individual that owns the sensitive data being used in the research project.
This is typically an NHS organisation, government body, or other institution that holds personal or sensitive data and has the legal authority to permit its use for research purposes.
The {term}`Data Owner` sets the conditions under which data may be used and must receive assurance that those conditions — including data deletion at project end — have been met.

#### Process responsibilities

- Receives the safe research plan from the {term}`Principal Investigator` and grants approval to use sensitive data.
- Feeds data governance requirements into {term}`FRIDGE Federation Governance`.
- Receives confirmation of project termination and data deletion from the {term}`Principal Investigator` at project close.
