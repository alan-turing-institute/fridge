---
short_title: Role Catalogue
---
# Role Catalogue

:::{glossary}
TRE Operator Organisation
: Operates the full stack TRE (sometimes called the front door TRE) and FRIDGE TRE, manages technical security controls, and may receive delegated approval authority from Data Provider.

FRIDGE Hosting Organisation
: Provisions and secures resources on FRIDGE hosting facility to host the {term}`Satellite TRE`.
  Specialisations might include:
  - Public Cloud hosting organisation (e.g. AWS, GCP, Azure)
  - A Private Cloud hosted by another organisation
  - National Facility (e.g. [AIRR](https://www.ukri.org/news/300-million-to-launch-first-phase-of-new-ai-research-resource/))
  
Resource Allocator
: Approves compute resource requests, and monitors resource utilisation of the supercomputing platform hosting the FRIDGE.

FRIDGE Federation Governance 
: Equivalent to ISO 27001 top management accountable for risk, determining requirements and monitoring performance. See [FRIDGE Governance](shared_gov_model.md).

Operational Management Group
: Representatives from the technical groups running FRIDGE, information governance and researchers as appropriate to manage risk in day-to-day operations. See [FRIDGE Governance](shared_gov_model.md).

Principal Investigator
: Leads research projects, submits Safe Project applications, and nominates researchers.

Safe Researcher
: Researcher who has completed training, signed attestation, and been approved for data access. This person is authorised to use the TRE.

Job Submitter
: A subset of {term}`Safe Researcher` who can submit FRIDGE jobs (i.e. dispatch jobs to a remote resource).

TRE Administrator
: Deploys FRIDGE components under responsibility of {term}`TRE Operator Organisation` (blue in the diagrams).
  A subset of {term}`FRIDGE Hosting Organisation`.

Infrastructure Provider Administrator
: Deploys FRIDGE components under responsibility of {term}`FRIDGE Hosting Organisation` (green in the diagrams).
  A subset of {term}`TRE Operator Organisation`.
:::
