#!/usr/bin/env bash

echo 'Uninstalling K3 cluster...'

# Unistall Cilium (recommended)
cilium uninstall

# Uninstall k3s
/usr/local/bin/k3s-uninstall.sh
