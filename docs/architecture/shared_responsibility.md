---
short_title: Shared Responsibility Model
---
# Shared Responsibility Model

```{figure} ../static/Fridge_Shared_Responsibility_Model.drawio.svg
---
name: fridge-shared-responsibility-diagram
alt: FRIDGE Shared Responsibility Model diagram
---
High-level view of the responsibilities shared between the 3 key organisations, mapped to the 5 safes
```

Security, governance and compliance in FRIDGE is a shared responsibility between the {term}`FRIDGE Hosting Organisation`, the {term}`TRE Operator Organisation`, and the {term}`Resource Allocator`. This shared model helps to distribute operational burden appropriately across parties:

- The {term}`FRIDGE Hosting Organisation` operates, manages and controls the components from the physical hardware and network infrastructure up to tenancy isolation and Kubernetes cluster management.
- The {term}`TRE Operator Organisation` assumes responsibility for the research environment built upon that foundation — including the TRE platform and code, identity and access management and encryption. Furthermore they retain all responsibility for governance processes such as output management and researcher accreditation.
- The {term}`Resource Allocator` retains responsibility for ensuring that projects and their associated workspace resource allocations are appropriate and justified.

Organisations should carefully consider their role within this model, as responsibilities vary depending on how FRIDGE services are integrated into existing TRE operations and the applicable legal, regulatory and data governance frameworks in place.


## Shared Processes and Infrastructure

While the shared responsibility model clearly delineates ownership, operating safely in practice requires a set of agreed cross-boundary processes. Responsibility for a control does not eliminate the need for coordination with other parties in exercising it.

A key example is infrastructure configuration: {term}`TRE Administrator`s define and approve the technical configurations required to maintain a secure environment, but the implementation of those configurations on the underlying infrastructure is carried out by the {term}`Hosting Administrator`. Neither party can fulfil their responsibilities in isolation.

These shared processes should be:

- Defined and agreed between relevant parties before the platform goes into operation, with clear handoff points, acceptance criteria, and escalation paths documented.
- Monitored through the {term}`Operational Management Group`, with evidence of process execution reported as part of regular risk and performance monitoring to Federation Governance.
- Automated wherever possible — manual handoffs introduce delay and risk of error; automation reduces both, and provides an auditable record of configuration changes.

Other shared processes requiring similar treatment include those described in the [FRIDGE lifecycle](./lifecycle.md).
