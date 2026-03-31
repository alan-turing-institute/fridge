---
short_title: Shared Responsibility Model
---
(arch-shared-responsibility)=
# Shared Responsibility Model

Security, governance and compliance in FRIDGE is a shared responsibility between the {term}`TRE Operator Organisation` and the{term}`FRIDGE Hosting Organisation`.
The {term}`Resource Allocator` also plays a more minor role in judging the suitability of a project.
A summary of the distribution of responsibilities, and their relation to the [5 Safes](https://ukdataservice.ac.uk/help/secure-lab/what-is-the-five-safes-framework/) is shown in [](#fig-shared-responsibility)

```{figure} ../static/shared_responsibility_model.drawio.svg
---
name: fig-shared-responsibility
alt: >
  A diagram showing the FRIDGE Shared Responsibility Model, organised into three horizontal layers mapped against the Five Safes framework.
  The Resource Allocator layer at the top covers Project Suitability and Workspace Resource Allocation, corresponding to Safe Projects.
  The TRE Provider Organisation layer in the middle covers Study Membership (Safe Projects), Safe Researcher Accreditation (Safe People), Data Lifecycle Management (Safe Data), Output Management (Safe Outputs), and a Safe Setting group comprising TRE Platform, TRE Code, Applications, Identity and Access Management, Client Side Encryption, and Network Traffic Protection.
  The FRIDGE Hosting Organisation layer at the bottom covers Tenancy Isolation, Kubernetes Clusters, Public IP Addressing, and Physical Hardware and Network, also mapped to Safe Setting.
---
A high-level view of the responsibilities shared between the three key organisations.
Each responsibility is mapped to one of the [5 Safes](https://ukdataservice.ac.uk/help/secure-lab/what-is-the-five-safes-framework/).
```

This shared model helps to distribute operational burden appropriately across parties:

- The {term}`TRE Operator Organisation` assumes responsibility for the research environment including the TRE platform and code, identity and access management, and encryption.
  Furthermore they retain all responsibility for governance processes such as output management and researcher accreditation.
- The {term}`FRIDGE Hosting Organisation` operates the physical and logical hosting environment for the satellite TRE, providing a secure tenancy to the {term}`TRE Operator Organisation`.
- The {term}`Resource Allocator` retains responsibility for ensuring that computing resources are allocated to the FRIDGE instance or on a per project basis.

Organisations should carefully consider their role within this model, as responsibilities vary depending on how FRIDGE services are integrated into existing TRE operations and the applicable legal, regulatory and data governance frameworks in place.


## Shared Processes

While the shared responsibility model clearly delineates ownership, operating safely in practice requires a set of agreed cross-boundary processes.
Responsibility for a control does not eliminate the need for coordination with other parties in exercising it.
Such shared processes are described in [](#arch-lifecycle).
