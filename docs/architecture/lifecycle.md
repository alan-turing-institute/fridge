---
short_title: Lifecycle
---
# FRIDGE Lifecycle and Data Flow

The series of sequence diagrams presented here outline the lifecycle of a FRIDGE instance and project.

## Project Initialisation

Before deploying and using a FRIDGE instance, the project must get approval for the use of sensitive data from the {term}`Data Owner` and receive an allocation of resources to use from the {term}`FRIDGE Hosting Organisation`.

:::{mermaid}
sequenceDiagram
  actor PI as Principal Investigator
  actor DO as Data Owner
  actor TO as TRE Operator Organisation
  actor FH as FRIDGE Hosting Organisation

  PI ->> DO: safe research plan
  DO ->> TO: approval to use data
  TO ->> FH: request FRIDGE account & allocation
  FH ->> TO: account and allocation
:::
