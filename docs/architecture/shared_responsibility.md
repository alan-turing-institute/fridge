(arch-shared-responsibility)=
# FRIDGE Shared Responsibility Model

```{figure} ../static/Fridge_Shared_Responsibility_Model.drawio.svg
---
name: fridge-shared-responsibility-diagram
alt: FRIDGE Shared Responsibility Model diagram
---
High-level view of the responsibilities shared between the 3 key organisations, mapped to the 5 safes
```

Security, governance and compliance in FRIDGE is a shared responsibility between the {term}`FRIDGE Hosting Organisation`, the {term}`TRE Operator Organisation`, and the {term}`Resource Allocator`. This shared model helps to distribute operational burden appropriately across parties:

- The {term}`FRIDGE Hosting Organisation` operates, manages and controls the components from the physical hardware and network infrastructure up to tenancy isolation and Kubernetes cluster management.
- The {term}`TRE Operator Organisation` assumes responsibility for the research environment built upon that foundation — including the TRE platform and code, identity and access management, encryption, output management, and researcher accreditation.
- The {term}`Resource Allocator` retains responsibility for ensuring that projects and their associated workspace resource allocations are appropriate and justified.

Organisations should carefully consider their role within this model, as responsibilities vary depending on how FRIDGE services are integrated into existing TRE operations and the applicable legal, regulatory and data governance frameworks in place.

## Shared Responsibility Scope

```{figure} ../static/FRIDGE_SRM_Scope.drawio.svg
---
name: fridge-shared-responsibility-scope
alt: FRIDGE Shared Responsibility Model scope diagram
---
Shows 2 shared responsibility models within the scope of the single TRE
```
In the example above the scope of a single TRE is extended from a cloud provider (covered by the cloud provider shared responsibility model) onto a FRIDGE super computing platform (covered byt the FRIDGE shared responsibility model)


