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

(use-api-s3-credentials)=
### S3 credentials

By default, the API reaches object storage with its own generic S3 identity.
That identity can only:

- upload to, list and delete from the `ingress` bucket
- read and list the `egress` bucket

So with the generic identity you cannot download from `ingress` or delete from `egress`.
This keeps data flowing one way: in through `ingress`, out through `egress`.

The object endpoints also accept your own S3 credentials, in the optional `X-S3-Access-Key` and `X-S3-Secret-Key` headers.
When you send them, the object storage checks what those credentials are allowed to do instead.
Both headers must be sent together.
They are in addition to the HTTP Basic credentials, not a replacement for them.

```console
curl -k -u "$FRIDGE_AUTH" \
  -H "X-S3-Access-Key: <access-key>" \
  -H "X-S3-Secret-Key: <secret-key>" \
  "$FRIDGE_URL/object/list?bucket=<bucket>"
```

Most Job Submitters will not need them.
At present, they are only needed by TRE Administrators for admin operations such as [creating a bucket](#use-api-housekeeping).
They are intended to support user-specific buckets in future.

In the interactive documentation, the two headers can be entered once in the "Authorize" dialog.

:::{note}
Like HTTP Basic authentication, this credential model is part of the current development design and may change.
:::

### Interactive documentation

The API serves interactive OpenAPI documentation at `$FRIDGE_URL/docs`, where you can read the full request and response schemas and try the endpoints.

## Overview of a job

Object storage has two buckets, `ingress` and `egress`.
Workflows run in the `argo-workflows` namespace and share a block storage volume that is mounted at `/data` in the data-copy workflow.
A typical job has these steps:

1. Upload input data to the `ingress` bucket.
2. Copy it from `ingress` to the block storage volume, unless the workflow reads it directly from object storage.
3. Submit a workflow from a template.
4. Check the workflow's status and logs.
5. Copy the results from the volume to the `egress` bucket.
6. Download the results.

Workflows can only write to `egress`, and the API's generic identity cannot read `ingress` back out.
This is deliberate: it stops a job from overwriting its own input data, and makes `egress` the only way out.

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
{"status": 201, "response": "input.csv"}
```

List what is in a bucket with:

```console
curl -k -u "$FRIDGE_AUTH" "$FRIDGE_URL/object/list?bucket=ingress"
```

`bucket` defaults to `ingress`.
With the generic identity, only `ingress` and `egress` can be listed; other buckets need your own [S3 credentials](#use-api-s3-credentials).
Add `prefix=<prefix>` to restrict the listing, and `recursive=true` to include objects below the top level.

### 2. Copy the data to the volume

Workflows can read their input either from the shared volume or directly from object storage.
To use the volume, copy the data onto it first.
The `/object/move` endpoint submits the `data-copy` workflow, which copies files from the bucket onto the volume.
If your workflow reads from object storage instead, skip this step (see [Reading directly from object storage](#use-api-artifacts)).

```console
curl -k -u "$FRIDGE_AUTH" -X POST \
  "$FRIDGE_URL/object/move?direction=ingress&files=input.csv"
```

To copy more than one file, separate the names with `;` (URL-encoded as `%3B`):

```console
curl -k -u "$FRIDGE_AUTH" -X POST \
  "$FRIDGE_URL/object/move?direction=ingress&files=a.csv%3Bb.csv"
```

File names must be relative, and must not contain `..`.
Before starting the copy, the API checks that every file exists in the bucket, and returns `404` naming the first missing file if not.

By default, files are copied from the `ingress` bucket.
To copy from a different bucket, add `bucket=<bucket>`; the API checks the files exist using your own [S3 credentials](#use-api-s3-credentials) if you send them.

The response names the bucket and the workflow that was started:

```json
{"status": 200, "direction": "ingress", "bucket": "ingress", "files": ["input.csv"], "workflow": "data-copy-x7k2q"}
```

The copy runs asynchronously.
Check that it has finished before you use the data, as described in [step 4](#use-api-status).

(use-api-artifacts)=
#### Reading directly from object storage

Argo Workflows is configured with the object storage as its default artifact repository, using the `ingress` bucket.
A workflow template can declare an S3 input artifact by key, and Argo fetches the object into the container before the step runs:

```yaml
inputs:
  artifacts:
    - name: input-data
      path: /scratch/input.csv
      s3:
        key: input.csv
```

Argo reads artifacts with its own S3 identity, which can read any bucket but only write to `egress`.
To read from a bucket other than `ingress`, set `bucket` under `s3`.
Output artifacts must likewise set `bucket: egress`, as writes to any other bucket are refused.

Whether a template reads from the volume or from object storage is decided by whoever writes the template.
Ask your TRE Administrators which approach the templates available to you use.

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
Results can only be copied to `egress`, so `bucket`, if given, must be `egress`.
The API cannot see the volume, so it does not check these files up front: if a file does not exist on the volume, the copy workflow fails and reports this in its log.

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
Object names can include `/`, for example `$FRIDGE_URL/object/egress/run-1/results.csv`.

(use-api-housekeeping)=
## Housekeeping

Delete an object from a bucket:

```console
curl -k -u "$FRIDGE_AUTH" -X DELETE "$FRIDGE_URL/object/ingress/input.csv"
```

With the generic identity, you can only delete from `ingress`.

Create an additional bucket.
This needs S3 admin rights, so you must send admin [S3 credentials](#use-api-s3-credentials); without them, the API returns `401`:

```console
curl -k -u "$FRIDGE_AUTH" -X POST \
  -H "X-S3-Access-Key: <admin-access-key>" \
  -H "X-S3-Secret-Key: <admin-secret-key>" \
  "$FRIDGE_URL/object/bucket?bucket_name=my-bucket"
```

Bucket names must follow the S3 rules: 3 to 63 characters, using lowercase letters, numbers, dots and hyphens, and starting and ending with a letter or number.

:::{note}
Data in other buckets can be copied onto the volume with `/object/move`, but results can only be copied out to `egress`.
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
| `GET` | `/object/list` | List objects in a bucket |
| `POST` | `/object/move` | Copy files between a bucket and the shared volume |
| `POST` | `/object/bucket` | Create a bucket. Requires admin S3 credentials |
| `DELETE` | `/object/{bucket}/{file_name}` | Delete an object |

`{file_name}` may contain `/`.
All of the `/object` endpoints accept the optional `X-S3-Access-Key` and `X-S3-Secret-Key` headers described in [S3 credentials](#use-api-s3-credentials).

## Errors

| Status | Meaning |
|---|---|
| `401` | Missing or incorrect credentials, or only one of the two S3 credential headers was sent. Also returned by `/object/bucket` when no S3 credentials are sent |
| `403` | The object storage refused access, for example downloading from `ingress` with the generic identity |
| `404` | The bucket, object, workflow or workflow template does not exist |
| `422` | Invalid request, for example an invalid bucket name, an absolute or `..` file path, or an empty file list |
| `500` | Another error, for example an upload that failed. The `detail` field gives the reason |

Errors from Argo Workflows are passed through with their original status code and a `detail` field.
For example, a namespace that does not exist or that you may not use returns an error like "Namespace not found or not permitted."
