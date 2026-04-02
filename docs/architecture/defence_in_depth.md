(arch-defence)=
# Defence in Depth

A FRIDGE instance is a {term}`TRE <Trusted Research Environment>` and so needs to be designed to provide a high level of protection.
Some aspects of security are enforced by the [Kubernetes clusters](#arch-arch-tenancy-network) and others at the [infrastructure level](#arch-arch-tenancy-requirements).
Therefore, responsibility for the security of FRIDGE is [shared](#arch-shared-responsibility) between the {term}`TRE Operator Organisation` and {term}`FRIDGE Hosting Organisation`.

A principle in the design of FRIDGE was defence in depth.
That is, that no single failure should make it possible for sensitive data to be exfiltrated from the TRE in an unauthorised manner.
Furthermore, the goal should be for security features to be enforced by two independent systems or roles so that a compromise of one is not sufficient to break security.

## Networking

Within the [Kubernetes clusters](#arch-arch-tenancy-network) network policy is [enforced by a CNI plugin](#arch-arch-internal-cni).
This ensures that only essential and intended traffic is permitted.
The default policy is to block all traffic, unless explicitly allowed.

The [networks](#arch-arch-tenancy-network) which host the cluster nodes must also strongly limit traffic.
In particular, traffic between the {term}`Access Network` and {term}`Isolated Network` is stricly limited to what is neccesary,
and the {term}`Isolated Network` can make no outbound connections except for pulling container images from the [](#arch-arch-internal-harbor).

The enforcing of network rules by two independent systems adds robustness.
If, for example, privilege escalation occurred inside Kubernetes, the Cilium network policies could be modified or bypassed.
However, the infrastructure-level networking restrictions would still prevent unauthorised data egress.

## Privilege Escalation

### In Kubernetes

FRIDGE uses Kubernetes [Role Based Access Control](https://kubernetes.io/docs/concepts/security/rbac-good-practices/).
[Roles](https://kubernetes.io/docs/reference/access-authn-authz/rbac/#role-and-clusterrole) which enable specific operations are bound to [Service Accounts](https://kubernetes.io/docs/concepts/security/service-accounts/) which are then assigned to individual pods.
This then allows certain pods to interact with the Kubernetes API in a limited way.

For example, the [](#arch-arch-internal-workflow) inherits a role which allows it to create jobs in the job namespace only.
This allows it to dispatch job requests from {term}`Job Submitters <Job Submitter>`, but not create resources in other namespaces or modify other FRIDGE components.

### On Cluster Nodes

The built in Kubernetes [Restricted](https://kubernetes.io/docs/concepts/security/pod-security-standards/#restricted) [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/) are applied to all namespaces, except those which need additional privileges.
Specifically, all pods launched by {term}`Job Submitters <Job Submitter>` must comply with the Restricted standard.
This prevents running as root, accessing host storage, and accessing the host network amongst other restrictions.

Compromising the host of a pod is therefore unlikely.
In the case that the host system was accessed, even as a privileged user, the network isolation enforced by the infrastructure would again prevent unauthorised data egress.
Sensitive data may be accessible, but would be encrypted.

## Data

Encryption of sensitive data at rest protects this data from being read as cleartext by those with access to the storage system.
