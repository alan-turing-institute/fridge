# FRIDGE

FRIDGE extends {term}`trusted research environments <Trusted Research Environment>` to powerful, external compute resources using an ephemeral, satellite {term}`TRE <Trusted Research Environment>` deployed in a secure enclave.

## Overview

{term}`TREs <Trusted Research Environment>` can be constrained by the computing resources available to them.
This could hinder research which requires high-performance hardware and accelerators, for example AI workloads.
Cloud and HPC systems possess great computational power but they are not useable for research with sensitive data if they lie outside the governance boundary of a {term}`TRE <Trusted Research Environment>`.
FRIDGE enables the use of computing power from external resources, such as cloud or cloud-native HPC, in an existing {term}`TRE <Trusted Research Environment>`.

FRIDGE extends the governance boundary of an existing {term}`TRE <Trusted Research Environment>` to the external resource.
This is achieved by provisioning a secure enclave to the external infrastructure into which the ephemeral FRIDGE satellite {term}`TRE <Trusted Research Environment>` is deployed.
In effect, a portion of the external system is borrowed by the {term}`TRE <Trusted Research Environment>` and brought under the control of the {term}`TRE <Trusted Research Environment>`, and its existing governance and administrators.

The advantage of this approach is, as we can formally consider the FRIDGE deployment part of an existing {term}`TRE <Trusted Research Environment>`, there is no need to involve the external infrastructure provider in data sharing agreements or rewrite existing agreements with data owners.
