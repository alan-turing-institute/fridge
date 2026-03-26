(arch-defence)=
# Defence in Depth

A FRIDGE instance is a {term}`TRE <Trusted Research Environment>` and so needs to be designed to provide a high level of protection.
Some aspects of security are enforced by the [Kubernetes clusters](#arch-arch-tenancy-network) and others at the [infrastructure level](#arch-arch-tenancy-requirements).
Therefore, responsibility for the security of FRIDGE is [shared](#arch-shared-responsibility) between the {term}`TRE Operator Organisation` and {term}`FRIDGE Hosting Organisation`.

A principle in the design of FRIDGE was defence in depth.
That is, that no single failure should make it possible for sensitive data to be exfiltrated from the TRE in an unauthorised manner.
Furthermore, the goal should be for security features to be enforced by two independent systems or roles so that a compromise of one is not sufficient to break security.

## Networking

- Network (Cilium)
- at infrastructure network (vnet) isolation (out of band!)

## Privilege Escalation

### In Kubernetes

- RBAC (and namespaces)

### On Cluster Nodes

- PSS
- Compromising the host is very unlikely
  - And even if it does happen, and privilege escalation occurs, there is no access to other networks
  - No access to data from other projects
  - The worst that can happen is a researcher trashes their own environment

## Data

- Data-at-rest encryption (protects from bad actors, compromise at infrastructure provider)
  _e.g._ access from host
