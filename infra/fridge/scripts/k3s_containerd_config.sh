#!/bin/sh
# Configure containerd in K3s to enable connecting to private registries
# and pull-through caches for public registries in Habor.
# This script is executed in the isolated cluster

HARBOR_HOSTNAME=$1 # e.g. harbor.fridge.local

echo "Configuring containerd to connect to Harbor..."

cat > /etc/rancher/k3s/registries.yaml << EOF
mirrors:
  docker.io:
    endpoint:
      - https://$HARBOR_HOSTNAME/v2/proxy-docker.io
  quay.io:
    endpoint:
      - https://$HARBOR_HOSTNAME/v2/proxy-quay.io
  ghcr.io:
    endpoint:
      - https://$HARBOR_HOSTNAME/v2/proxy-ghcr.io
configs:
  $HARBOR_HOSTNAME:
    tls:
      insecure_skip_verify: true
EOF

echo "Restarting K3s for changes to take effect..."
systemctl restart k3s
