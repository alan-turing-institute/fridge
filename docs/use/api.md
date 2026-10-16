(use-api)=
# Using the FRIDGE API

The FRIDGE API is how {term}`Job Submitters <Job Submitter>` move data in and out of a FRIDGE and run workflows on it.
This page explains how to connect to it and walks through a typical job.

The API is a thin layer over two services in the {term}`Isolated Cluster`: Argo Workflows, which runs the jobs, and the S3-compatible object storage, which holds the data.
Users never talk to either service directly.

:::{warning}
FRIDGE is under active development, and parts of the API's access model are temporary development arrangements rather than the intended production design.
In particular, the way you authenticate to the API and the way its TLS certificate is issued are both expected to change.
Treat the [authentication](#use-api-auth) and TLS details on this page as describing the current behaviour only, and check with your TRE Administrators before relying on them.
The endpoints and the workflow described below are expected to be more stable.
:::

## Connecting

The API is only reachable over the NetBird VPN.
Your device must be a peer in the group that has access to the FRIDGE API, as described in [Configuring NetBird](../deploy/netbird.md).
Your {term}`TRE Administrators <TRE Administrator>` can tell you which group to use and give you the NetBird address of the access cluster peer.

Requests go to port `8000` of that address.
The access cluster forwards them without inspecting them to the API in the isolated cluster, which serves HTTPS.

```console
export FRIDGE_URL=https://<netbird-address>:8000
```

:::{important}
At present, the API's TLS certificate is issued by a certificate authority internal to the FRIDGE and is only valid for the API's internal IP address, not for the NetBird address.
Your client will therefore refuse to verify it.
The examples below use `curl -k` to skip verification; equivalent options exist in other clients (for example `verify=False` in Python `requests`).

This is a development-time arrangement and the certificate model is expected to change.
Avoid building certificate-verification workarounds into long-lived scripts.
:::

(use-api-auth)=
### Authentication

At present, every endpoint except the health checks uses HTTP Basic authentication.
The username and password are the `fridge_api_admin` and `fridge_api_password` values set when the isolated cluster was deployed (see [Configuration Reference](../deploy/configuration.md)).
Your TRE Administrators will provide them.

```console
export FRIDGE_AUTH='<username>:<password>'
curl -k -u "$FRIDGE_AUTH" "$FRIDGE_URL/object/list"
```

A wrong username or password returns `401 Invalid credentials`.

:::{note}
HTTP Basic authentication with a single shared account is a stopgap for development, used until a better approach is chosen.
It may be replaced in production deployments, so the API does not currently distinguish between users.
Until then, treat the credentials as you would any other shared secret.
:::

### Interactive documentation

The API serves interactive OpenAPI documentation at `$FRIDGE_URL/docs`, where you can read the full request and response schemas and try the endpoints.

## Overview of a job

Object storage has two buckets, `ingress` and `egress`.
Workflows run in the `argo-workflows` namespace and share a block storage volume that is mounted at `/data` in the data-copy workflow.
A typical job has these steps:

1. Upload input data to the `ingress` bucket.
2. Copy it from `ingress` to the block storage volume.
3. Submit a workflow from a template.
4. Check the workflow's status and logs.
5. Copy the results from the volume to the `egress` bucket.
6. Download the results.

Workflows can read from `ingress` and write to `egress`, but not the reverse.
This is deliberate: it stops a job from overwriting its own input data.

## Worked example

### 1. Upload data

Upload a file to the `ingress` bucket.
The object is stored under the file's name.

```console
curl -k -u "$FRIDGE_AUTH" \
  -F "file=@input.csv" \
  "$FRIDGE_URL/object/ingress/upload"
```

```json
{"status": 201, "response": "input.csv", "version": "None"}
```

List what is in a bucket with:

```console
curl -k -u "$FRIDGE_AUTH" "$FRIDGE_URL/object/list?bucket=ingress"
```

`bucket` is either `ingress` (the default) or `egress`.
Add `prefix=<prefix>` to restrict the listing, and `recursive=true` to include objects below the top level.

### 2. Copy the data to the volume

Workflows read their input from the shared volume, not directly from object storage.
The `/object/move` endpoint submits the `data-copy` workflow, which copies files from the bucket onto the volume.

```console
curl -k -u "$FRIDGE_AUTH" -X POST \
  "$FRIDGE_URL/object/move?direction=ingress&files=input.csv"
```

To copy more than one file, separate the names with `;` (URL-encoded as `%3B`):

```console
curl -k -u "$FRIDGE_AUTH" -X POST \
  "$FRIDGE_URL/object/move?direction=ingress&files=a.csv%3Bb.csv"
```

The response names the workflow that was started:

```json
{"status": 200, "direction": "ingress", "files": ["input.csv"], "workflow": "data-copy-x7k2q"}
```

The copy runs asynchronously.
Check that it has finished before you use the data, as described in [step 4](#use-api-status).

### 3. Submit a workflow

First find out which workflow templates are available, and what parameters they take:

```console
curl -k -u "$FRIDGE_AUTH" "$FRIDGE_URL/workflowtemplates/argo-workflows"
```

```json
[
  {
    "namespace": "argo-workflows",
    "template_name": "my-analysis",
    "parameters": [{"name": "input-file", "value": "input.csv"}]
  }
]
```

Details of a single template are at `/workflowtemplates/argo-workflows/<template_name>`.

Then submit a workflow from the template, giving values for the parameters:

```console
curl -k -u "$FRIDGE_AUTH" -X POST \
  -H "Content-Type: application/json" \
  -d '{
        "namespace": "argo-workflows",
        "template_name": "my-analysis",
        "parameters": [{"name": "input-file", "value": "input.csv"}]
      }' \
  "$FRIDGE_URL/workflowevents/from_template/"
```

The response includes the name, namespace, status and creation time of the new workflow.
Parameters you leave out keep the default value defined in the template.

(use-api-status)=
### 4. Check status and logs

List all workflows in the namespace:

```console
curl -k -u "$FRIDGE_AUTH" "$FRIDGE_URL/workflows/argo-workflows"
```

Or look at a single workflow:

```console
curl -k -u "$FRIDGE_AUTH" "$FRIDGE_URL/workflows/argo-workflows/<workflow_name>"
```

The `status` field is the Argo workflow phase, for example `Running`, `Succeeded`, `Failed` or `Error`.
Add `verbose=true` to either request to get Argo's complete workflow description instead of the summary.

Fetch the log of a workflow with:

```console
curl -k -u "$FRIDGE_AUTH" "$FRIDGE_URL/workflows/argo-workflows/<workflow_name>/log"
```

By default this returns the log of the `main` container of the pod with the same name as the workflow, which is the pod of a single-step workflow.
For workflows with several steps, pass `pod_name=<pod>` to select a particular pod, and `container_name=<container>` to select a container other than `main`.

### 5. Copy the results out

Have your workflow write its results to the shared volume at `/data`.
When the workflow has succeeded, copy the results to the `egress` bucket with `direction=egress`:

```console
curl -k -u "$FRIDGE_AUTH" -X POST \
  "$FRIDGE_URL/object/move?direction=egress&files=results.csv"
```

The file names are relative to `/data`.
If a file does not exist on the volume, the copy workflow fails and reports this in its log.

:::{important}
Like the copy into the FRIDGE, this runs as a workflow.
Wait for `data-copy-...` to reach `Succeeded` before downloading.
:::

### 6. Download the results

```console
curl -k -u "$FRIDGE_AUTH" -OJ "$FRIDGE_URL/object/egress/results.csv"
```

The file is streamed back as an attachment.
Use `target_file=<name>` to set a different file name in the download.

## Housekeeping

Delete an object from a bucket:

```console
curl -k -u "$FRIDGE_AUTH" -X DELETE "$FRIDGE_URL/object/ingress/input.csv"
```

Create an additional bucket:

```console
curl -k -u "$FRIDGE_AUTH" -X POST "$FRIDGE_URL/object/bucket?bucket_name=my-bucket"
```

:::{note}
Workflows are only granted access to the `ingress` and `egress` buckets, so data in other buckets cannot be copied onto the volume or out of it.
:::

## Endpoint reference

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/workflows/{namespace}` | List workflows |
| `GET` | `/workflows/{namespace}/{workflow_name}` | Get one workflow |
| `GET` | `/workflows/{namespace}/{workflow_name}/log` | Get a workflow's log |
| `GET` | `/workflowtemplates/{namespace}` | List workflow templates and their parameters |
| `GET` | `/workflowtemplates/{namespace}/{template_name}` | Get one workflow template |
| `POST` | `/workflowevents/from_template/` | Submit a workflow from a template |
| `POST` | `/object/{bucket}/upload` | Upload a file (multipart form field `file`) |
| `GET` | `/object/{bucket}/{file_name}` | Download an object |
| `GET` | `/object/list` | List objects in `ingress` or `egress` |
| `POST` | `/object/move` | Copy files between a bucket and the shared volume |
| `POST` | `/object/bucket` | Create a bucket |
| `DELETE` | `/object/{bucket}/{file_name}` | Delete an object |

## Errors

| Status | Meaning |
|---|---|
| `401` | Missing or incorrect credentials |
| `403` | The object storage refused access to the bucket |
| `404` | The bucket, object, workflow or workflow template does not exist |
| `500` | Another error, for example an upload that failed. The `detail` field gives the reason |

Errors from Argo Workflows are passed through with their original status code and a `detail` field.
For example, a namespace that does not exist or that you may not use returns an error like "Namespace not found or not permitted."
