(arch-data)=
# Data Flow

[](#fig-data-flow)

```figure ../static/data-storage-layout.png
---
name: fig-data-flow
alt: >
    A diagram showing the flow of data through a FRIDGE.
    Data passes from the home TRE to object storage inside the FRIDGE via the FRIDGE API.
    From there, Argo Workflows can move it to encrypted block storage.
    It can then be loaded for use in Argo Workflows processing jobs.
    Outputs from Argo Workflow jobs can be transferred back to block storage.
    From there they can be retrieved from the home TRE using the FRIDGE API.
---

```
