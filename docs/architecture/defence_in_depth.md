(sec-arch-defence)=
# Defence in Depth

- Defence in depth
  - at K8s
    - PSS
    - Network (Cilium)
    - RBAC
    - Data-at-rest encryption (protects from bad actors, compromise at infrastructure provider)
  - at infrastructure
    - network (vnet) isolation (out of band!)
  - Compromising the host is very unlikely
    - And even if it does happen, and privilege escalation occurs, there is no access to other networks
    - No access to data from other projects
    - The worst that can happen is a researcher trashes their own environment
