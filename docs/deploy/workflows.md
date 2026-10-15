# Creating workflows

FRIDGE deploys Argo `WorkflowTemplate` resources as part of the isolated-cluster infrastructure. The repository's built-in templates live in `infra/fridge/isolated-cluster/k8s/argo_workflows/templates.yaml` and are loaded by the Pulumi isolated-cluster stack.

## Add a workflow template

To add a workflow that should be available in a FRIDGE deployment:

1. Add an Argo `WorkflowTemplate` to `infra/fridge/isolated-cluster/k8s/argo_workflows/templates.yaml`.
2. Set the template namespace to `argo-workflows` and use the `argo-workflow` service account unless the workflow has different requirements.
3. If the workflow needs the shared workflow-data volume, define a volume named `workflow-data-ingress` with a placeholder persistent-volume claim. During deployment, the Pulumi stack replaces that claim with the provisioned FRIDGE block-storage claim.
4. Redeploy the isolated-cluster infrastructure so the updated template is applied to the cluster.

The existing `data-copy` template is a useful reference for the expected structure.

## Access MinIO from a workflow

MinIO is available to workloads inside the cluster at:

```text
https://minio.argo-artifacts.svc.cluster.local
```

FRIDGE's existing `data-copy` workflow mounts the `trusted-certificates` secret into `/etc/ssl/certs` so HTTPS clients can validate the MinIO certificate. Workflows that connect to MinIO directly should use the same trust bundle rather than disabling certificate verification.

For example, add the certificate volume to the workflow template:

```yaml
volumes:
  - name: ssl-certs
    secret:
      secretName: trusted-certificates
```

and mount it in the container:

```yaml
volumeMounts:
  - name: ssl-certs
    mountPath: /etc/ssl/certs
    readOnly: true
```

Use the `ingress` bucket for data entering the isolated environment and the `egress` bucket for data leaving it, following the access pattern in the built-in `data-copy` template.

## Shared workflow data volume

The isolated-cluster Pulumi program rewrites the `workflow-data-ingress` volume in workflow templates to point at the block-storage PVC created for Argo workflows. A template that needs that volume can therefore use the same placeholder pattern as `data-copy`:

```yaml
volumes:
  - name: workflow-data-ingress
    persistentVolumeClaim:
      claimName: replace_me
```

and mount it where the workflow expects its working data:

```yaml
volumeMounts:
  - name: workflow-data-ingress
    mountPath: /data
```

The placeholder is replaced during deployment; it should not be changed to a hard-coded PVC name.
