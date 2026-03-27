(arch-arch)=
# Architecture

## Legend

In the following diagrams we use colours to indicate who has access or control over particular resources.
These are mapped to our [roles](#arch-roles),

- {span .role .tre-operator}``(blue) owned by {term}`TRE Operator Organisation` ``
- {span .role .hosting-provider}``(green) owned by {term}`FRIDGE Hosting Organisation` ``
- {span .role .job-submitter}``(orange) used by {term}`Job Submitter`s, owned by {term}`TRE Operator Organisation` ``

{span .role .external}`pink` items indicate externally controlled resources, outside of the scope of our [roles](#arch-roles).

Arrows indicate the flow of permitted traffic.
Solid lines indicate pushes, that is, they are triggered from the beginning of the arrow.
Dotted lines indicate pulls, triggered from the end of the arrow.

(arch-arch-satellite)=
## Satellite TRE

[](#fig-satellite) demonstrates the high-level concept of a {term}`Satellite TRE`.
It shows the connection of an existing TRE to a {term}`Satellite TRE` instance deployed remote infrastructure.

The secure {term}`TRE Tenancy` boundary enables the {term}`extension of existing governance to the satellite TRE <Governance Boundary Extension>`.
On the remote infrastructure, a dashed line indicate the boundary of the {term}`TRE Tenancy`.
All resources within the tenancy are within the governance domain of the {term}`Home TRE`, through the {term}`Governance Boundary Extension` agreed in the {term}`Shared Responsibility` model.

:::{figure} ../static/satellite_tre.drawio.svg
---
label: fig-satellite
alt: >
  A block diagram depicting a satellite TRE.
  It shows how the satellite TRE is an adjunct to an existing TRE.
  The TRE admins configure the satellite TRE on remote infrastructure, while the remote infrastructure admins configure the TRE tenancy.
  TRE Researchers are able to dispatch jobs and manage data from their home TRE workspace.
---

A schematic of the {term}`Satellite TRE` concept, showing the home TRE and {term}`TRE Tenancy`.
:::

(arch-arch-tenancy)=
## FRIDGE and TRE Tenancy

### Overview

[](#fig-tenancy) gives an overview of the design of FRIDGE.
Compared to [](#fig-satellite), [](#fig-tenancy) reveals detail of the structure of a FRIDGE {term}`Satellite TRE`.
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

The dual-network design forms an important part of our approach to [](#arch-defence), in addition to K8s-native network control.
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

For {term}`Job Submitter`s, the local API interface and FRIDGE proxy provide transparent access to the FRIDGE API.
It will appear to them as a service in the network of their TRE workspace with endpoints for submitting and managing jobs dispatched to the FRIDGE instance.
Similarly, {term}`TRE Administrator`s are able to manage the K8s components of their FRIDGE instance through their own API interface.

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

The FRIDGE API provides users with endpoints to manage data, and submit and monitor jobs.
Writing a custom API separates {term}`Job Submitter`s from the underlying implementation, so that they may use a single FRIDGE interface irrespective.
This API will then be resilient to changes to the FRIDGE [](#arch-arch-internal-workflow) and storage.
It will also enable the creation of user-focused FRIDGE tools such as CLIs or web interfaces for job submission and management.

(arch-arch-internal-workflow)=
### Workflow Manager

The workflow manager receives job specifications from the [](#arch-arch-internal-api) and launches [jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/) in the [](#arch-arch-internal-jobns).
The workflow manager is an instance of [Argo Workflows](https://argoproj.github.io/workflows/).

(arch-arch-internal-jobns)=
#### Job Namespace

To isolate {term}`Job Submitter`s' processes from the rest of the {term}`Isolated Cluster`, including components which enforce security, jobs may only be run in a dedicated namespace.
This namespace has no access to external resources, other than research data and container images, and jobs are restricted to run without privileges.

(arch-arch-internal-harbor)=
### Container Repository

An instance of the [Harbor](https://goharbor.io/) container registry provides access to container images for the isolated cluster.
It acts both as a read-through cache for allowed public registries (such as Docker Hub, Quay and GitHub Container Registry) and as a repository for {term}`Job Submitter`s' own container images.
This allows {term}`Job Submitter`s to easily use custom software, by building a container image and pushing to the repository.

### Storage

#### Storage classes

FRIDGE defines two storage classes.
One is for holding sensitive data, and the other for non-sensitive data.
These storage classes need to be implemented for each target platform, as the appropriate [CSI](https://kubernetes.io/docs/concepts/storage/volumes/#csi) and options will vary.

For secure storage, if an available CSI supports encryption with keys provided by Kubernetes, that can be used.
Otherwise, FRIDGE can deploy Longhorn which will create Kubernetes volumes, backed by block storage, with data encrypted at rest.

#### Object storage

An object storage system is used for managing data assets in the FRIDGE instance.
This provides a convenient way to handle the ingress of inputs and egress of results.

Buckets are created for inputs and results.
The inputs bucket is read-only to jobs, to prevent the corruption of input data.

The object storage is provided by an instance of [Minio](https://www.min.io/) and uses a volume of the secure storage class for its backend.

#### Secure volumes

For higher performance than object storage, encrypted block devices can be accessed directly by jobs.

#### Insecure volumes

Unencrypted volumes are used by the [](#arch-arch-internal-harbor) for caching container images.

## Glossary

:::{glossary}
Access Cluster
: A Kubernetes cluster with services to manage the connection of the {term}`Home TRE` to the {term}`Isolated Cluster`, where sensitive-data workloads are run.
  It also hosts the [](#arch-arch-internal-harbor) which enable the {term}`Isolated Cluster` to pull container images, despite being isolated.

Access Network
: The [FRIDGE network](#arch-arch-tenancy-network) hosting the {term}`Access Cluster`.
  This network acts as a bridge connecting the {term}`Home TRE` to FRIDGE job execution components.

Container Runtime
: The [container runtime](https://kubernetes.io/docs/setup/production-environment/container-runtimes/) is the component of a Kubernetes distribution which is responsible for running containers.
  Between distributions, the particular container runtime may differ, but all will communicate with Kubernetes through a standard interface.

  In FRIDGE, it is important that the container runtime of the {term}`Isolated Cluster` is configured to fetch container images from the [container repository](#arch-arch-internal-harbor), as it will not be able to access public container registries.

Home TRE
: An existing TRE, complete with infrastructure, data governance and processes.
  Research questions are established in this TRE, before data and job specifications are dispatched to the {term}`Satellite TRE` for execution.
  The {term}`Satellite TRE` formally belongs within the governance boundary of the home TRE.

Isolated Cluster
: A Kubernetes cluster with services to run workloads on sensitive data, and manage inputs and results

Isolated Network
: The [FRIDGE network](#arch-arch-tenancy-network) hosting the {term}`Isolated Cluster`.
  This network creates a secure boundary around the FRIDGE components which run sensitive-data workloads.
  It is a key part of the [security of a FRIDGE instance](#arch-defence).
:::
