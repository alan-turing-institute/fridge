---
short_title: Introduction
---
# Architecture and Governance

This section details the architecture and governance of a FRIDGE deployment.
It explains the basic concepts underpinning FRIDGE, details of the governance roles and processes, and the technical architecture.

## Key Concepts

There are a number of concepts central to FRIDGE that are important to understand.

:::{glossary}
Trusted Research Environment
: A secure computational environment designed for conducting research on sensitive data.
  TREs must balance an appropriate level of security for the data being processed,
  and usability to enable researchers to work effectively and efficiently.

  FRIDGE assumes an existing TRE, with its own security controls and governance.
  FRIDGE places few requirements on that TRE other than establishing a connection to a FRIDGE instance.

Satellite TRE
: An adjunct to an existing TRE that provides extra functionality or computational resources.
  A satellite TRE is not a full TRE itself, and requires a home TRE to operate.

  FRIDGE is an example of a satellite TRE.

Roles
: The operation of a FRIDGE instance depends on people, most likely, split between multiple organisations.
  Their responsibilities and access form a key part of FRIDGE's security and governance.
  As such, we have defined [roles](#arch-roles) for FRIDGE and outlined their scope and purpose.
  This scheme helps clarify who is responsible for infrastructure or processes irrespective of which organisation they belong to or what their job title is.

Governance Boundary Extension
: The integration of resources owned by an external organisation into the control and governance of an existing TRE.
  Asserting the TREs governance over the satellite TRE is essential for the operation of FRIDGE, and avoiding complex data sharing agreements between the {term}`Data Owner`, {term}`TRE Operator Organisation`, and {term}`FRIDGE Hosting Organisation`.
  This arrangement is enabled by FRIDGE's technical and governance security controls.

TRE Tenancy
: The components that form the secure enclave into which the satellite TRE can be deployed.
  The tenancy must ensure that data, processes and network traffic inside are opaque to,

  1. the host system
  1. other tenancies.

Shared Responsibility
: As the FRIDGE infrastructure, is split between organisations, there is no single organisation that takes sole responsibility for a FRIDGE instance and its operation.
  The shared responsibility model defines the boundaries of each organisations responsibility.
  For efficient operation it is important that the {term}`TRE Operator Organisation` retains responsibility for data processing.
  However, it is not possible to remove all responsibility from the {term}`FRIDGE Hosting Organisation`, for example in deploying a secure {term}`TRE Tenancy`.

  The general principle of FRIDGE is to minimise the responsibility of the {term}`FRIDGE Hosting Organisation`.

Defence in Depth
: The use of multiple layers of security control so that if one control is broken or circumvented, the overall system remains secure.
  The worst-case scenario is the unauthorised egress of data from a FRIDGE instance.
  In FRIDGE we aim for no single point of failure and have ensured that no single failure would, on its own, lead to that outcome.

Five Safes
: The [Five Safes Framework](https://ukdataservice.ac.uk/help/secure-lab/what-is-the-five-safes-framework/) sets out a method for understanding the range of factors affecting data security in research.
  It can be used as a guide to designing or assessing TREs.
  The framework splits data security into five components, safe data, safe projects, safe people, safe settings, and safe outputs.
:::
