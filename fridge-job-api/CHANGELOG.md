# Changelog

## [0.9.0]

- **Breaking:** `POST /object/{bucket}/upload`, which took the file as a multipart form field, is replaced by `PUT /object/{bucket}/{file_name}`, which takes the file as the raw request body (e.g. `curl -T data.csv .../object/ingress/data.csv`). The object's content type is taken from the `Content-Type` header, and the request must have a `Content-Length` header
- Uploads are streamed to S3 as they arrive, instead of saving the whole request to disk before the upload to S3 starts. Files over 16MB are sent to S3 as a multipart upload with several parts in parallel, and smaller files in a single request
- Uploads reject object names that are absolute or contain `..`
- New multipart upload endpoints under `/uploads/{bucket}`: the client sends the file in numbered parts, in parallel if it likes, and can resume an interrupted upload by listing the parts already uploaded and sending the rest
- Objects can be up to 1TiB, whichever way they are uploaded
- The upload data held in memory across all requests is limited to 1GiB. An upload that would go over this is refused with a 503 and a `Retry-After` header before any of it is read
- Added `examples/upload.py`, an example client for the multipart upload endpoints
- Endpoints that make blocking calls to Argo or S3, and the readiness probe, now run in a thread pool, so they no longer hold up other requests (such as uploads in progress) while they wait

## [0.8.0]

- Object endpoints (`upload`, `get`, `list`, `delete`, `/object/move`) accept the caller's own S3 credentials in the optional `X-S3-Access-Key` and `X-S3-Secret-Key` headers, so S3 enforces what they may do (e.g. that only the owner can use a user-specific bucket). If omitted, the API's generic S3 credentials are used. This is for potential future enablement of user-specific buckets.
- The API's generic S3 identity can only upload to, list and delete from `ingress`, and read and list `egress`. It has no admin rights
- `/object/bucket` (bucket creation) takes the admin's S3 credentials in the same headers, so the API itself no longer holds S3 admin rights. These are the `fridge-admin` S3 identity, set by the new `s3_admin_access_key` and `s3_admin_secret_key` stack config values on the isolated cluster, which the bucket setup job also uses
- `/object/move` accepts a `bucket` for ingress copies, checks the files exist, and rejects empty names, absolute paths and `..`
- Object keys containing `/` can now be downloaded and deleted
- Removed unused object versioning support: the `versioning` parameter on `/object/bucket`, the `version` parameter on object get, delete and move, and the `version` field in upload responses
- The `data-copy` workflow passes its parameters through environment variables and authenticates to S3 with the `fridge-argo` identity (the anonymous S3 identity is removed)

## [0.7.0]

- Removed MinIO code paths and replaced with generic S3 codepaths
- STS authentication via K8s API no longer used as not supported by SeaweedFS

## [0.6.0]

- Allows users to list files in the ingress and egress buckets

## [0.5.1]

- Fix issue where MinIO auth token expired after one hour, so readiness check would fail

## [0.5.0]

- Added `healthz` and `readyz` endpoints for Kubernetes health and readiness probes

## [0.4.0]

- Fixed handling of MinIO SSL certificates
- Added functionality for copying files to the `egress` bucket
