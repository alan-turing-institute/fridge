# Let's Encrypt staging roots

Public root certificates for the Let's Encrypt **staging** environment, from
<https://letsencrypt.org/docs/staging-environment/>:

- `letsencrypt-stg-root-x1.pem`: (STAGING) Pretend Pear X1 (RSA)
- `letsencrypt-stg-root-x2.pem`: (STAGING) Bogus Broccoli X2 (ECDSA)

When `tls_environment` is `staging`, these are exported as `harbor_ca_bundle` so
that the isolated cluster's containerd can verify Harbor's certificate.

These roots must only be trusted for staging deployments, and only for the
Harbor registry host. Do not add them to a system trust store.
