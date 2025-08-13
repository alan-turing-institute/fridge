#!/usr/bin/env bash

# Deploy a vanilla K3s cluster
# Flannel CNI, network policy, kube-proxy and Traefik are disabled
# to allow Cilium to handle all these
#
curl -sfL https://get.k3s.io | sh -s - \
  --flannel-backend none \
  --disable-network-policy \
  --disable-kube-proxy \
  --disable=traefik \
  --cluster-init

mkdir -p ~/.kube; \
  sudo cat /etc/rancher/k3s/k3s.yaml > ~/.kube/config; \
  echo 'export KUBECONFIG=~/.kube/config' >> .bashrc; \
  source .bashrc

# Setup architecture
ARCH=amd64; if [ "$(uname -m)" = "aarch64" ]; then ARCH=arm64; fi

# Cilium

curl -OL https://github.com/cilium/cilium-cli/releases/download/v0.18.6/cilium-linux-${ARCH}.tar.gz
sudo tar xvfC cilium-linux-${ARCH}.tar.gz /usr/local/bin
cilium install \
  --version 1.17.6 \
  --set ipam.operator.clusterPoolIPv4PodCIDRList="10.42.0.0/16" \
  --set kubeProxyReplacement=true \
  --set k8sServiceHost=127.0.0.1 \
  --set k8sServicePort=6443

cilium status --wait
cilium hubble enable

## Longhorn
## See: https://longhorn.io/docs/1.9.1/deploy/install/#installing-open-iscsi

curl -sSfL -o longhornctl https://github.com/longhorn/cli/releases/download/v1.9.1/longhornctl-linux-${ARCH}
chmod +x longhornctl
./longhornctl install preflight
./longhornctl check preflight

# Add the following entries to local /etc/hosts file
# Replace <vm-ip> with IP of VM hosting K3s
#
# <vm-ip>  argo.fridge.internal
# <vm-ip>  minio.fridge.internal
# <vm-ip>  harbor.fridge.internal
