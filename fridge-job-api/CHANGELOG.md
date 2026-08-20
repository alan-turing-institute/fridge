# Changelog

## [0.5.1]

- Fix issue where MinIO auth token expired after one hour, so readiness check would fail

## [0.5.0]

- Added `healthz` and `readyz` endpoints for Kubernetes health and readiness probes

## [0.4.0]

- Fixed handling of MinIO SSL certificates
- Added functionality for copying files to the `egress` bucket
