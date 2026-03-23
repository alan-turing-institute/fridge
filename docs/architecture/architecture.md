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

[](#fig-satellite) demonstrates the high-level concept of a {term}`satellite TRE`.
It shows the connection of an existing TRE to a {term}`satellite TRE` instance deployed remote infrastructure.

The secure {term}`TRE tenancy` boundary enables the {term}`extension of existing governance to the satellite TRE <Governance Boundary Extension>`.
On the remote infrastructure, a dashed line indicate the boundary of the {term}`TRE tenancy`.
All resources within the tenancy are within the governance domain of the {term}`Home TRE`, through the {term}`governance boundary extension` agreed in the {term}`shared responsibility` model.

:::{figure} ../static/satellite_tre.drawio.svg
:label: fig-satellite
:alt: A block diagram depicting a satellite TRE. It shows how the satellite TRE is an adjunct to an existing TRE. The TRE admins configure the satellite TRE on remote infrastructure, while the remote infrastructure admins configure the TRE tenancy. TRE Researchers are able to dispatch jobs and manage data from their home TRE workspace.

A schematic of the {term}`satellite TRE` concept, showing the home TRE and {term}`TRE Tenancy`.
:::

## FRIDGE

### Overview

[](#fig-tenancy) gives an overview of the design of FRIDGE.
Compared to [](#fig-satellite), [](#fig-tenancy) reveals detail of the structure of a FRIDGE {term}`satellite TRE`.
It shows how management traffic is isolated from research traffic and part of how the {term}`TRE Tenancy` is defined through network isolation.

:::{figure} ../static/high_level.drawio.svg
:label: fig-tenancy
:alt: A block diagram depicting a high-level overview of FRIDGE architecture. Shown at the home TRE, FRIDGE instance and the TRE Tenancy boundary. Arrows show the direction of data flow.

A high-level overview of a FRIDGE instance, showing the home TRE and {term}`TRE Tenancy`.
:::

### Requirements

[](#fig-tenancy) represents a generic FRIDGE deployment, and specific details may vary between implementations.
However, there are some requirements which must be met by all implementations,

- No traffic is allowed between the {term}`Access Network` and {term}`Isolated Network` except for,
  - Kube Proxy to Kube API,
  - FRIDGE Proxy to FRIDGE API,
  - Container Runtime to Container Repository.
- No outbound traffic is allowed from the {term}`Isolated Network`, except for that described above.
- No outbound traffic is allowed from the {term}`Access Network`, except to select container repositories.
- Both the {term}`Access Network` and {term}`Isolated Network` must be isolated from other networks on the {term}`FRIDGE Hosting Organisation's <FRIDGE Hosting Organisation>` infrastructure.
- On a cloud-like system, the {term}`TRE Tenancy` must be isolated from any other tenancies.
  For example, it must not be possible to share resources from the {term}`TRE Tenancy` with other tenants.

### Dual Network

The FRIDGE instance is split into two networks, each of which contains a K8s cluster.
The {term}`Access Cluster` is responsible for routing traffic from the {term}`Home TRE` to the {term}`Isolated Cluster`.
The {term}`Isolated Cluster` has access to sensitive data, and runs jobs on that data.
Traffic between the two clusters is strongly restricted by a firewall, with only the connections shown in [](#fig-tenancy) permitted.
In addition, the {term}`Isolated Network` has no outbound access, beyond the {term}`Container Runtime` being able to pull container images from the {term}`Container Repository` in the {term}`Access Network`.

The dual-network design forms an important part of our approach to [](#sec-arch-defence), in addition to K8s-native network control.
In the event of container breakout, or otherwise compromising the K8s nodes, there is still no route to exfiltrate sensitive data.

### Connection from Home TRE

#### Bastion

To avoid publicly exposing the Kube API of the {term}`Access Cluster`, some sort of bastion (for example a virtual machine running an SSH server, or wireguard) should be used.
The nature of this bastion may vary between implementations.

#### Router and Ingress

To correctly route traffic intended for the {term}`Access Cluster`, a router or reverse proxy is used.
This may route traffic based on port, hostname, prefix or some combination.
The nature of this may vary between implementations.
All must point to the {term}`Access Cluster` where a [K8s Ingress Controller](https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/) will direct traffic to the correct service.

#### Proxies

For {term}`Job Submitters`, the local API interface and FRIDGE proxy provide transparent access to the FRIDGE API.
It will appear to them as a service in the network of their TRE workspace with endpoints for submitting and managing jobs dispatched to the FRIDGE instance.
Similarly, {term}`TRE Administrators` are able to manage the K8s components of their FRIDGE instance through their own API interface.

The proxies and {term}`Access Cluster's <Access Cluster>` Kube API are distinct pods.
Proxy pods run an SSH daemon and are used to pass requests through to the {term}`Isolated Cluster's <Isolated Cluster>` Kube API or FRIDGE API via an SSH tunnel.
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
