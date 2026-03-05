---
short_title: Lifecycle
---
# FRIDGE Lifecycle and Data Flow

- Diagram of data flow
    - immutable inputs
    - working space backed by encrypted performant block storage
    - write-only outputs deposited in bucket
    - Workflow templates
- Security
    - Buckets for input and outputs
    - Different permissions based on RBAC
    - input
        - API:  RW
        - Service AC (researchers): RO
    - egress
        - API: RW
        - Service AC (researchers):  WO
    - inputs are immutable
