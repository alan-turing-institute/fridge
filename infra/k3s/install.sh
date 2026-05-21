#!/usr/bin/env bash

# Deploy a vanilla K3s cluster
# Flannel CNI, network policy, kube-proxy and Traefik are disabled
# to allow Cilium to handle all these
echo 'Installing K3s...'

# Configure containerd for private registry before K3s installation
echo 'Configuring containerd registry settings...'
HARBOR_HOSTNAME="${1:-harbor.fridge.internal}"  # Use argument or default

sudo mkdir -p /etc/rancher/k3s
sudo tee /etc/rancher/k3s/registries.yaml > /dev/null <<EOF
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

curl -sfL https://get.k3s.io | sh -s - \
  --flannel-backend none \
  --disable-network-policy \
  --disable-kube-proxy \
  --disable=traefik \
  --cluster-init

# Copy kube config to home directory to access the cluster without sudo
mkdir -p ~/.kube; \
  sudo cat /etc/rancher/k3s/k3s.yaml > ~/.kube/config; \
  echo 'export KUBECONFIG=~/.kube/config' >> ~/.bashrc; \
  export KUBECONFIG=~/.kube/config

# Setup architecture
ARCH=amd64
if [ "$(uname -m)" = "aarch64" ]; then
  ARCH=arm64
fi

# Cilium
echo 'Installing Cilium...'

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

echo 'K3s cluster is now ready for FRIDGE deployment'
echo
echo '** Run the following command for KUBECONFIG to take effect in this shell session'
echo 'source ~/.bashrc'
echo
echo 'Copy the contents of ~/.kube/config to the host machine if required.'
echo
echo 'Also add the following entries to the /etc/hosts file of the host machine'
echo 'Replace <vm-ip> with IP of this K3s VM. The VM must be reachable from the host machine on this IP'
echo '** Note that these urls are configured in the corresponing Pulumi configuration for the K3s stack'
echo
echo '<vm-ip>>  argo.fridge.internal'
echo '<vm-ip>>  minio.fridge.internal'
echo '<vm-ip>>  harbor.fridge.internal'
