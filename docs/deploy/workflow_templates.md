(use-workflow-templates)=
# Creating Workflow Templates

{term}`Job Submitters <Job Submitter>` run jobs on a FRIDGE by submitting workflows through the [FRIDGE API](./api.md).
They can only submit workflows from Argo Workflows [`WorkflowTemplate`s](https://argo-workflows.readthedocs.io/en/latest/workflow-templates/) that already exist in the {term}`Isolated Cluster`.
The API cannot create or replace templates, so the set of deployed templates decides what code can run on the FRIDGE.

This page is for {term}`TRE Administrators <TRE Administrator>`.
It explains how to write a template that works within the constraints of the isolated cluster, and how to deploy it.

## Where templates run

Argo Workflows only runs workflows in the `argo-workflows` namespace.
Every template must:

- set `metadata.namespace: argo-workflows`
- set `spec.serviceAccountName: argo-workflow`

The `argo-workflow` service account has only the permissions Argo needs to report results.
Do not give it, or a new service account, further permissions.

## Constraints on workflow pods

Workflow pods run under several restrictions.
Most template failures come from one of them.

### Security context

The `argo-workflows` namespace enforces the Kubernetes [restricted Pod Security Standard](https://kubernetes.io/docs/concepts/security/pod-security-standards/#restricted).
Argo applies a default security context to every container, so you do not have to set one.
Containers run as user and group `8737`, without root, privilege escalation or extra capabilities.

As a result:

- the image must work when run as an arbitrary non-root user
- the container can only write to mounted volumes, `/tmp` and other world-writable locations, not to its home directory or the image's install paths. Setting `HOME` to `/tmp`, as in the example below, fixes most tools that write caches or configuration to the home directory
- GPU devices may need an extra group, set at pod level with `spec.securityContext.supplementalGroups`. For example, the AMD GPU examples add group `992`

### Network

Workflow pods have no internet access.
They can only reach:

- DNS, and only to resolve the object storage service
- the object storage S3 endpoint
- the Kubernetes API, which Argo uses to report results
- other workflow pods labelled `ddp-job`, for multi-node distributed training

So a workflow cannot download packages, models or data at run time.
Everything it needs must be in the image or in the job's input data.

### Images

The isolated cluster pulls images through the Harbor registry in the {term}`Access Cluster`, which caches images from:

- `docker.io`
- `ghcr.io`
- `quay.io`
- `registry.k8s.io`

Use images from one of these registries, and pin them to a tag or digest so that a template always runs the same code.
Large images, such as GPU builds of PyTorch, may need a larger `harbor_registry_size` (see [Configuration Reference](../deploy/configuration.md)).

## Data

A workflow can read its input and write its results in two ways.
The template's author chooses which, and Job Submitters need to know which one a template uses.
See [Using the FRIDGE API](./api.md) for how data moves in and out of the FRIDGE.

### Shared volume

The `/object/move` endpoint copies files between object storage and a block storage volume, the persistent volume claim `block-storage-pvc`.
Files are copied to and from the root of the volume, keeping their object names.

To use it, mount `block-storage-pvc` in your template.
Write results to the volume too, so that Job Submitters can copy them to `egress` with `/object/move`.

### Object storage artifacts

Argo's default artifact repository is the `ingress` bucket.
Declare input artifacts from `ingress` by key, and Argo fetches them before the step runs.
The default repository also supplies the endpoint, credentials and internal CA, so these artifacts need no extra configuration.

```yaml
inputs:
  artifacts:
    - name: input-data
      path: /tmp/input.csv
      s3:
        key: input.csv
```

Output artifacts must go to the `egress` bucket, as Argo can only write to `egress`.
An artifact in any bucket other than `ingress` does not use the default repository, so setting `bucket: egress` alone is not enough.
It must give the full S3 configuration: the endpoint, region, credentials and the internal CA.

```yaml
outputs:
  artifacts:
    - name: results
      path: /tmp/results.csv
      s3:
        endpoint: seaweedfs-s3.seaweedfs.svc.cluster.local:8334
        region: eu-west-2
        bucket: egress
        key: results.csv
        accessKeySecret:
          name: argo-artifacts-s3
          key: accesskey
        secretKeySecret:
          name: argo-artifacts-s3
          key: secretkey
        caSecret:
          name: trusted-certificates
          key: ca-certificates.crt
```

The region is not a real region, only a placeholder needed for S3 compatibility.
The same applies to input artifacts read from `egress` or any other bucket.

### Object storage from inside a container

A container can also talk to object storage directly, for example with `curl`, the AWS CLI or `boto3`, at `https://seaweedfs-s3.seaweedfs.svc.cluster.local:8334`.
The object storage's TLS certificate is issued by a certificate authority internal to the FRIDGE, which is not in the image's trust store, so these connections fail certificate verification unless you provide the internal CA.

The CA is available in the `argo-workflows` namespace as the `trusted-certificates` secret.
Its single key, `ca-certificates.crt`, holds the internal CA together with the standard public CAs.
Mount it over the image's system trust store:

```yaml
volumes:
  - name: ssl-certs
    secret:
      secretName: trusted-certificates
templates:
  - name: main
    container:
      env:
        # For tools that do not use the system trust store, such as the AWS CLI, boto3 and requests
        - name: AWS_CA_BUNDLE
          value: /etc/ssl/certs/ca-certificates.crt
        - name: REQUESTS_CA_BUNDLE
          value: /etc/ssl/certs/ca-certificates.crt
        - name: SSL_CERT_FILE
          value: /etc/ssl/certs/ca-certificates.crt
      volumeMounts:
        - name: ssl-certs
          mountPath: /etc/ssl/certs
          readOnly: true
```

Mounting at `/etc/ssl/certs` replaces that directory, which suits Debian- and Ubuntu-based images.
Images that keep their trust store elsewhere need the environment variables, or the equivalent for their tools.
Do not turn off certificate verification instead.

The container also needs S3 credentials.
The `argo-artifacts-s3` secret holds Argo's own credentials, under the keys `accesskey` and `secretkey`, which can read any bucket and write only to `egress`.
The `data-copy` template shows how to pass both the CA and the credentials to a container.

## Parameters

The API lists, and lets Job Submitters set, only the parameters under `spec.arguments.parameters`.
Give every parameter a sensible default, as parameters a Job Submitter leaves out keep it.

Treat parameter values as untrusted input.
Pass them to the container as environment variables, not by substituting them into a shell script, so that a value cannot inject shell commands.
The `data-copy` template in `infra/fridge/isolated-cluster/k8s/argo_workflows/templates.yaml` shows this pattern.

## Example

This template runs a Python script that a Job Submitter has copied onto the shared volume, and writes its output back to the volume.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: WorkflowTemplate
metadata:
  name: run-python-script
  namespace: argo-workflows
spec:
  entrypoint: main
  serviceAccountName: argo-workflow
  arguments:
    parameters:
      - name: script
        value: analysis.py
  volumes:
    - name: block-storage
      persistentVolumeClaim:
        claimName: block-storage-pvc
  templates:
    - name: main
      inputs:
        parameters:
          - name: script
      container:
        image: python:3.13-slim
        env:
          - name: SCRIPT
            value: "{{inputs.parameters.script}}"
          - name: HOME
            value: /tmp
        command: ["sh", "-c"]
        args:
          - |
            cd /data
            python "$SCRIPT"
        volumeMounts:
          - name: block-storage
            mountPath: /data
```

More examples are in `infra/fridge/isolated-cluster/k8s/argo_workflows/examples/`.

## Deploying a template

Templates are deployed with `kubectl` against the isolated cluster.
As when [deploying the isolated cluster](../deploy/services.md), you must be connected to the NetBird VPN and use the isolated cluster's Kubernetes context.

Check the template against the cluster without creating it:

```console
kubectl --context <isolated-cluster-context> apply --dry-run=server -f run-python-script.yaml
```

Then deploy it:

```console
kubectl --context <isolated-cluster-context> apply -f run-python-script.yaml
```

To update a template, edit the file and apply it again.
Workflows that are already running are not affected.

Check that the template is available to Job Submitters through the API:

```console
curl -k -u "$FRIDGE_AUTH" "$FRIDGE_URL/workflowtemplates/argo-workflows/run-python-script"
```

Before handing a template over, submit a workflow from it through the API and check that it reaches `Succeeded`, as described in [Using the FRIDGE API](./api.md).
Failures caused by the constraints above, such as permission errors when writing files or failed network connections, show up in the workflow's log.

To remove a template:

```console
kubectl --context <isolated-cluster-context> delete workflowtemplate -n argo-workflows run-python-script
```

:::{important}
The `data-copy` template is deployed by the isolated cluster's Pulumi stack, and the API uses it for `/object/move`.
Do not edit or delete it with `kubectl`: the next `pulumi up` will undo any change.
Templates you deploy with `kubectl` are not managed by Pulumi, so keep their files under version control.
:::
