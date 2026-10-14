# Changelog

## [Unreleased]

- Object endpoints (`upload`, `get`, `list`, `delete`, `/object/move`) accept the caller's own S3 credentials in the optional `X-S3-Access-Key` and `X-S3-Secret-Key` headers, so S3 enforces what they may do (e.g. that only the owner can use a user-specific bucket). If omitted, the API's generic S3 credentials are used
- The API's generic S3 identity is limited to the shared `ingress` and `egress` buckets and has no admin rights
- `/object/bucket` (bucket creation) takes the admin's S3 credentials in the same headers, so the API itself no longer holds S3 admin rights
- `/object/move` accepts a `bucket` for ingress copies, checks the files exist, and rejects empty names, absolute paths and `..`
- Object keys containing `/` can now be downloaded and deleted
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
