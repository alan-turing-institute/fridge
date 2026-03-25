(arch-arch)=
# Architecture

## Legend

In the following diagrams we use colours to indicate who has access or control over particular resources.
These are mapped to our [roles](#arch-roles),

- {span .role .tre-operator}``(blue) owned by {term}`TRE Operator Organisation` ``
- {span .role .hosting-provider}``(green) owned by {term}`FRIDGE Hosting Organisation` ``
- {span .role .job-submitter}``(orange) used by {term}`Job Submitters`, owned by {term}`TRE Operator Organisation` ``

{span .role .external}`pink` items indicate externally controlled resources, outside of the scope of our [roles](#arch-roles).

Arrows indicate the flow of permitted traffic.
Solid lines indicate pushes, that is, they are triggered from the beginning of the arrow.
Dotted lines indicate pulls, triggered from the end of the arrow.

(arch-arch-satellite)=
## Satellite TRE

[](#fig-satellite) demonstrates the high-level concept of a {term}`satellite TRE`.
It shows the connection of an existing TRE to a {term}`satellite TRE` instance deployed remote infrastructure.

The secure {term}`TRE tenancy` boundary enables the {term}`extension of existing governance to the satellite TRE <Governance Boundary Extension>`.
On the remote infrastructure, a dashed line indicate the boundary of the {term}`TRE tenancy`.
All resources within the tenancy are within the governance domain of the {term}`Home TRE`, through the {term}`governance boundary extension` agreed in the {term}`shared responsibility` model.

:::{figure} ../static/satellite_tre.drawio.svg
---
label: fig-satellite
alt: >
  A block diagram depicting a satellite TRE.
  It shows how the satellite TRE is an adjunct to an existing TRE.
  The TRE admins configure the satellite TRE on remote infrastructure, while the remote infrastructure admins configure the TRE tenancy.
  TRE Researchers are able to dispatch jobs and manage data from their home TRE workspace.
---

A schematic of the {term}`satellite TRE` concept, showing the home TRE and {term}`TRE Tenancy`.
:::

(arch-arch-tenancy)=
## FRIDGE and TRE Tenancy

### Overview

[](#fig-tenancy) gives an overview of the design of FRIDGE.
Compared to [](#fig-satellite), [](#fig-tenancy) reveals detail of the structure of a FRIDGE {term}`satellite TRE`.
It shows how management traffic is isolated from research traffic and part of how the {term}`TRE Tenancy` is defined through network isolation.

:::{figure} ../static/high_level.drawio.svg
---
label: fig-tenancy
alt: >
  A block diagram depicting a high-level overview of FRIDGE architecture.
  Shown at the home TRE, FRIDGE instance and the TRE Tenancy boundary.
  Arrows show the direction of data flow.
---

A high-level overview of a FRIDGE instance, showing the home TRE and {term}`TRE Tenancy`.
:::

(arch-arch-tenancy-requirements)=
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

(arch-arch-tenancy-network)=
### Dual Network

The FRIDGE instance is split into two networks, each of which contains a K8s cluster.
The {term}`Access Cluster` is responsible for routing traffic from the {term}`Home TRE` to the {term}`Isolated Cluster`.
The {term}`Isolated Cluster` has access to sensitive data, and runs jobs on that data.
Traffic between the two clusters is strongly restricted by a firewall, with only the connections shown in [](#fig-tenancy) permitted.
In addition, the {term}`Isolated Network` has no outbound access, beyond the {term}`Container Runtime` being able to pull container images from the [container repository](#arch-arch-internal-harbor) in the {term}`Access Network`.

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

(arch-arch-internal)=
## FRIDGE internal

:::{figure} ../static/internal.drawio.svg
---
label: fig-internal
alt: >
  A block diagram showing the internal components of FRIDGE K8s clusters.
---

A diagram showing the key internal components of the FRIDGE Kubernetes clusters.
Lines indicate access to private volumes.
:::

### Network Policy

Network traffic within the FRIDGE clusters is restricted.
This is achieved using [Cilium](https://cilium.io/) [CNI plugin](https://kubernetes.io/docs/concepts/extend-kubernetes/compute-storage-net/network-plugins/).
This is in addition to the network isolation enforced by the [networks](#arch-arch-tenancy-network).

### TLS

[cert-manager](https://cert-manager.io/) will automatically provision and renew TLS certificates for services which can be reached over HTTPS.
For example, the [container repository](#arch-arch-internal-harbor).

### Proxies

(arch-arch-internal-api)=
### FRIDGE API

- fast API

### Workflow Manager

The workflow manager receives job specifications from the [](#arch-arch-internal-api) and launches [jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/) in the [](#arch-arch-internal-jobns).

(arch-arch-internal-jobns)=
#### Job Namespace

To isolate {term}`Job Submitters' <Job Submitters>` processes from the rest of the {term}`Isolated Cluster`, including components which enforce security, jobs may only be run in a dedicated namespace.
This namespace has no access to external resources, other than research data and container images, and jobs are restricted to run without privileges.

(arch-arch-internal-harbor)=
### Container Repository

An instance of the [Harbor](https://goharbor.io/) container registry provides access to container images for the isolated cluster.
It acts both as a read-through cache for allowed public registries (such as Docker Hub, Quay and GitHub Container Registry) and as a repository for {term}`Job Submitters' <Job Submitters>` own container images.
This allows {term}`Job Submitters` to easily use custom software, by building a container image and pushing to the repository.

### Storage

#### Object storage

- Used for getting data in and results out
- Buckets for ingress (read only), egress
- Uses secure PVs as backend

#### Secure block storage

- Higher performance storage
- Can be accessed directly for jobs
- If CSI supports encryption with user-provider keys, that can be used
- Otherwise Longhorn, which supports encryption

#### Insecure block storage

- For harbor

## Glossary

:::{glossary}
Access Cluster
: …

Access Network
: The [FRIDGE network](#arch-arch-tenancy-network) hosting the {term}`Access Cluster`.
  This network acts as a bridge connecting the {term}`Home TRE` to FRIDGE job execution components.

Container Runtime
: The [container runtime](https://kubernetes.io/docs/setup/production-environment/container-runtimes/) is the component of a Kubernetes distribution which is responsible for running containers.
  Between distributions, the particular container runtime may differ, but all will communicate with Kubernetes through through a standard interface.

  In FRIDGE, it is important that the container runtime of the {term}`Isolated Cluster` is configured to fetch container images from the [container repository](#arch-arch-internal-harbor), as it will not be able to access public container registries.

Home TRE
: An existing TRE, complete with infrastructure, data governance and processes.
  Research questions are established in this TRE, before data and job specifications are dispatched to the {term}`satellite TRE` for execution.
  The {term}`satellite TRE` formally belongs within the governance boundary of the home TRE.

Isolated Cluster
: …

Isolated Network
: …
:::
