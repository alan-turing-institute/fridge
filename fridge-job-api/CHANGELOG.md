# Changelog

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
