(arch-roles)=
# Roles

:::{glossary}
TRE Operator Organisation
: Operates Front Door TRE and FRIDGE TRE, manages technical security controls, and may receive delegated approval authority from Data Provider.
  See Safe Setting Process, Safe Project Process, and Safe Researcher Process.

FRIDGE Hosting Organisation
: Provisions and secures resources on FRIDGE hosting facility (AIRR infrastructure).
  Specialisations include:
  - Public Cloud hosting organisation (e.g. AWS, GCP, Azure)
  - Private Cloud provided by the TRE Operator Organisation
  - National Facility (e.g. AIRR)
  
  See Safe Setting Process and Safe Project Process.

Resource Allocator
: Approves compute resource requests, ensures projects align with AIRR objectives, and monitors resource utilisation.
  Responsible for capacity and demand management.
  See Safe Setting Process and Safe Project Process.

Top Management
: Within the scope of FRIDGE, this role represents the "Organisation" covered by top management, which includes the extended governance boundary.
  See Governing FRIDGE.
  Source: SATRE.

Operational Management Group
: Representatives from all four key organisations (Resource Allocator, FRIDGE Hosting Organisation, TRE Operator Organisation, Data Provider).
  Coordinates day-to-day operations, addresses cross-organisational issues, and escalates strategic issues to Top Management.

Principal Investigator
: Leads research projects, submits Safe Project applications, and nominates researchers.

Safe Researcher
: Researcher who has completed training, signed attestation, and been approved for data access.
  This person is authorised to use the TRE.
  Source: Safe Researcher Process.

Job Submitter
: A subset of {term}`Safe Researcher` who can submit FRIDGE jobs (i.e. dispatch jobs to a remote resource).
  Within the scope of the FRIDGE architecture, this role requires the data consumer role.
  See Safe Project Process.

TRE Administrator
: Deploys FRIDGE components under responsibility of {term}`TRE Operator Organisation` (blue in the diagrams).

Infrastructure Provider Administrator
: Deploys FRIDGE components under responsibility of {term}`FRIDGE Hosting Organisation` (green in the diagrams).
  A subset of {term}`FRIDGE Hosting Organisation`.
:::
