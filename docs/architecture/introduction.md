---
short_title: Introduction
---
# Architecture and Governance

This section details the architecture and governance of a FRIDGE deployment.
It explains the basic concepts underpinning FRIDGE, details of the governance roles and processes, and the technical architecture.

## Executive Summary

TREs can be constrained by the computing resources available to them.
This could hinder research.
FRIDGE enables the use of computing power from external resources, such as cloud or HPC, in an existing TRE.

The approach to solving this problem is to extend the governance boundary of an existing TRE to the external resource.
This is achieved by provisioning a secure enclave to the external infrastructure into which the FRIDGE runner components are deployed.
In effect, a portion of the external system is borrowed by the TRE and brought under the control of the TRE, and its existing governance and administrators.

The advantage of this approach is, as we can formally consider the FRIDGE deployment part of an existing TRE, there is no need to involve the external infrastructure provider in data sharing agreements or rewrite existing agreements with data owners.

## Key Concepts

There are a number of concepts central to FRIDGE that are important to understand.

:::{glossary}
Trusted Research Environment
: …

Governance Extension
: …

Shared Responsibility
: …

Defence in Depth
: …

Roles
: …

5 Safes
: …
:::
