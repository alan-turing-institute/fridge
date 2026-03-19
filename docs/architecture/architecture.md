# Architecture

## Legend

In the following diagrams we use colours to indicate who has access or control over particular resources.
These are mapped to our [roles](#arch-roles),

- {span .role .job-submitter}``orange: {term}`Job Submitters` ``
- {span .role .tre-operator}``blue: {term}`TRE Operator Organisation` ``
- {span .role .hosting-provider}``green: {term}`FRIDGE Hosting Organisation` ``

{span .role .external}`pink` items indicate externally controlled resources, outside of the scope of our [roles](#arch-roles).

Arrows indicate the flow of permitted traffic.
Solid lines indicate pushes, that is, they are triggered from the beginning of the arrow.
Dotted lines indicate pulls, triggered from the end of the arrow.

## Satellite TRE and TRE Tenancy

### Overview

[](#fig-tenancy) gives a high-level overview of a FRIDGE deployment.
It demonstrates the {term}`satellite TRE` concept, showing the connection of an existing TRE to a FRIDGE instance deployed onto remote infrastructure.

On the remote infrastructure, a dashed line indicate the boundary of the {term}`TRE tenancy`.
All resources within the tenancy are within the governance domain of the {term}`Home TRE`, through the {term}`governance boundary extension` agreed in the {term}`shared responsibility` model.

:::{figure} ../static/high_level.drawio.svg
:label: fig-tenancy
:alt: A block diagram depicting a high-level overview of FRIDGE architecture. Shown at the home TRE, FRIDGE instance and the TRE Tenancy boundary. Arrows show the direction of data flow.

A high-level overview of a FRIDGE instance, showing the home TRE and {term}`TRE Tenancy`.
:::

### Dual Network

The FRIDGE instance is split into two networks, each of which contains a K8s cluster.
The {term}`Access Cluster` is responsible for routing traffic from the {term}`Home TRE` to the {term}`Isolated Cluster`.
The {term}`Isolated Cluster` has access to sensitive data, and runs jobs on that data.
Traffic between the two clusters is strongly restricted by a firewall, with only the connections shown in [](#fig-tenancy) permitted.
In addition, the {term}`Isolated Network` has no outbound access, beyond the {term}`Container Runtime` being able to pull container images from the {term}`Container Repository` in the {term}`Access Network`.

The dual-network design forms an important part of our approach to [](#sec-arch-defence), in addition to K8s-native network control.
In the event of container breakout, or otherwise compromising the K8s nodes, there is still no route to exfiltrate sensitive data.

### Connection to Home TRE

For {term}`Job Submitters`, the local API interface and FRIDGE proxy provide transparent access to the FRIDGE API.
It will appear to them as a service in the network of their TRE workspace with endpoints for submitting and managing jobs dispatched to the FRIDGE instance.
Similarly, {term}`TRE Administrators` are able to manage the K8s components of their FRIDGE instance through their own API interface.

The proxies and {term}`Access Cluster's <Access Cluster>` Kube API are distinct services, each served on different …

Proxy pods run an SSH daemon and are used to pass requests through to the {term}`Isolated Cluster's <Isolated Cluster>` Kube API or FRIDGE API via an SSH tunnel
Each API Interface at the {term}`Home TRE` is required to generate an SSH key pair.
Hence by installing the correct public key on each proxy, the {term}`TRE Operator Organisation` can control who has access to the APIs in the {term}`Isolated Cluster`.
It would also be possible to further restrict traffic through network controls such as IP allowlists or exposing the {term}`Access Cluster` only through a VPN.

## FRIDGE internal

- Update figure to cover access/isolated clusters, remove unused components
- Access cluster
    - user stuff
        - kube proxy (sshd)
        - FRIDGE proxy (sshd)
        - container repository (harbor)
    - others
        - Network policy (cilium)
- Isolated cluster
    - user stuff
        - FRIDGE API (fast api)
        - workflow manager (argo workloads)
        - job namespace
        - object storage (minio)
        - block storage (longhorn/CSI driver PVCs)
    - others
        - Network policy (cilium)

## Glossary

:::{glossary}
Access Cluster
: …

Access Network
: …

Container Repository
: …

Container Runtime
: …

Home TRE
: …

Isolated Cluster
: …

Isolated Network
: …
:::
