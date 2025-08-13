#!/usr/bin/env bash

# Make sure to set the Longhorn delete-confirmation flag to 'true before
# shutting down the k3s cluster (set value field to "true")
kubectl -n longhorn-system edit settings.longhorn.io deleting-confirmation-flag

# Unistall Cilium (recommended)
cilium uninstall

# Uninstall k3s
/usr/local/bin/k3s-uninstall.sh
