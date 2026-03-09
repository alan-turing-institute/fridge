---
short_title: Lifecycle
---
# FRIDGE Lifecycle and Data Flow

The series of sequence diagrams presented here outline the lifecycle of a FRIDGE instance and project.

(arch-lifecycle-init)=
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

After the [](#arch-lifecycle-init) a FRIDGE instance may be deployed.
The {term}`TRE Operator Organisation` triggers the {term}`TRE Administrators` and {term}`Hosting Provider Administrators` to deploy the TRE (if it isn't already), FRIDGE instance, and connect them.
Once this is complete, the {term}`Principal Investigators` will be informed the FRIDGE instance is ready to be used.

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
  TA ->> TA: Connect TRE to FRIDGE
  TA ->> TO: TRE deployment complete
  TO ->> PI: TRE details
:::

## FRIDGE research loop

With the TRE connected, the research team can now dispatch jobs to the FRIDGE instance.

The {term}`Principal Investigators` are able to upload the sensitive input data to immutable storage.

The {term}`Safe Researchers` can now work using FRIDGE in the loop,

1. Identify question
2. Design and submit job specification
3. Check job progress
4. Retrieve outputs

:::{mermaid}
sequenceDiagram
    actor PI as Principal Investigator
    actor SR as Safe Researcher
    actor JS as Job Submitter
    participant AC as FRIDGE API
    participant IC as FRIDGE

    PI->>AC: upload input data
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

## FRIDGE teardown

When there is no longer the need for a FRIDGE, the {term}`Principal Investigators` request the instance teardown.
The {term}`TRE Operator Organisation` instructs the  {term}`TRE Administrators` and {term}`Hosting Provider Administrators` to conduct the teardown.

:::{mermaid}
sequenceDiagram
  actor PI as Principal Investigator
  actor TO as TRE Operator Organisation
  actor TA as TRE Administrators
  actor HA as Hosting Administrators
  participant AC as Access Cluster
  participant IC as Isolated Cluster

PI ->> TO: report finished with FRIDGE
TO ->> TA: request FRIDGE release
TA ->> TA: disconnect TRE from FRIDGE
TA ->> HA: request FRIDGE teardown
activate HA
HA ->> AC: teardown
HA ->> IC: teardown
deactivate HA
HA ->> TO: teardown complete
:::

## Project termination

Finally, with the teardown complete the {term}`TRE Operator Organisation` and {term}`FRIDGE Hosting Organisation` must finalise the FRIDGE allocation.
Guarantees that and sensitive data has been deleted (or is otherwise unrecoverable) must be passed back to the {term}`TRE Operator Organisation` and {term}`Data Owner` to meet their data protection and data sharing agreement obligations.

:::{mermaid}
sequenceDiagram
  actor DO as Data Owner
  actor PI as Principal Investigator
  actor TO as TRE Operator Organisation
  actor FH as FRIDGE Hosting Organisation

FH ->> FH: close FRIDGE allocation
FH ->> TO: confirm FRIDGE allocation closure
FH ->> TO: confirm data deletion
TO ->> PI: share data deletion confirmation
PI ->> DO: confirm project termination<br /> and data deletion
:::
