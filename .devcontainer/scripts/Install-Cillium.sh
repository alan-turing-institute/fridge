#!/bin/bash
set -e
# Print message function
print_message() {
  echo "================================================================================"
  echo ">>> $1"
  echo "================================================================================"
}

cilium version
cilium install --version 1.17.6 --set=ipam.operator.clusterPoolIPv4PodCIDRList="10.42.0.0/16" --set=hubble.relay.enabled=true
