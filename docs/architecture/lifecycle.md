---
short_title: Lifecycle
---
# FRIDGE Lifecycle and Data Flow

The series of sequence diagrams presented here outline the lifecycle of a FRIDGE instance and project.

## Project Initialisation

Before deploying and using a FRIDGE instance, the project must get approval for the use of sensitive data from the {term}`Data Owner` and receive an allocation of resources to use from the {term}`FRIDGE Hosting Organisation`.

:::{mermaid}
sequenceDiagram
  actor DO as Data Owner
  actor PI as Principal Investigator
  actor TO as TRE Operator Organisation
  actor FH as FRIDGE Hosting Organisation

  PI ->> DO: safe research plan
  DO ->> PI: approval to use data
  PI ->> TO: request TRE workspace with FRIDGE
  TO ->> FH: request FRIDGE account & allocation
  FH ->> TO: account and allocation
  TO ->> PI: allocation details
:::

## FRIDGE provisioning

:::{mermaid}
sequenceDiagram
  actor PI as Principal Investigator
  actor TO as TRE Operator Organisation
  actor TA as TRE Administrators
  actor HA as Hosting Administrators
  participant AC as Access Cluster
  participant IC as Isolated Cluster

  TO ->> TA: request TRE deployment
  TA ->> TA: deploy TRE
  TA ->> HA: request FRIDGE
  activate HA
  HA ->> AC: deploy
  HA ->> IC: deploy
  HA ->> TA: connection details
  deactivate HA
  TA ->> AC: deploy satellite TRE
  TA ->> IC: deploy satellite TRE
  TA ->> HA: request lockdown
  activate HA
  HA ->> AC: apply lockdown
  HA ->> IC: apply lockdown
  HA ->> TA: lockdown complete
  deactivate HA
  TA ->> TO: TRE deployment complete
  TO ->> PI: TRE details
:::

## FRIDGE research loop

:::{mermaid}
sequenceDiagram
    actor PI as Principle Investigator
    actor SR as Safe Researcher
    actor JS as Job Submitter
    participant AC as FRIDGE API
    participant IC as FRIDGE

    PI->>AC: upload sensitive data
    AC->>IC: provision immutable data

    JS->>AC: push custom container images

    loop Researcher loop
        SR->>SR: research in TRE
        SR->>JS: research question for FRIDGE
        JS->>AC: submit job specification
        AC->>IC: launch job
        IC->>IC: run job
        IC->>IC: store results
        JS->>AC: check job status
        AC->>IC: get job status
        AC->>JS: job status
        JS->>AC: download results
        AC->>IC: get results
        AC->>JS: results
        JS->>SR: share results
    end
:::
