#!/usr/bin/env bash

# Deploy a vanilla K3s cluster
# Flannel CNI, network policy, kube-proxy and Traefik are disabled
# to allow Cilium to handle all these
echo 'Installing K3s...'

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
cilium hubble enable --ui

# Dex
# Dex is used as an OIDC provider in dev environments only and deployed outside the FRIDGE K8s cluster
echo 'Installing Dex...'

sudo dnf -y install dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo dnf -y install docker-ce docker-ce-cli containerd.io
sudo systemctl enable --now docker

export HOST_IP=$(ip -brief address show lima0 | awk '{print $3}' | awk -F/ '{print $1}')

mkdir -p dex
cat config.dex.yaml | envsubst > dex/config.yaml
sudo docker run \
  --rm -d \
  --name dex \
  --net=host \
  --volume ./dex:/tmp/dex \
  --entrypoint dex ghcr.io/dexidp/dex serve /tmp/dex/config.yaml

echo 'K3s cluster is now ready for FRIDGE deployment'
echo
echo '** Run the following command for KUBECONFIG to take effect in this shell session'
echo 'source ~/.bashrc'
echo
echo 'Copy the contents of ~/.kube/config to the host machine if required.'
echo
echo 'The OIDC details for the local Dex instance are:'
echo '  Issuer URL:     http://'$HOST_IP':5556/dex'
echo '  Client Id:      argo-workflows'
echo '  Client Secret:  argo-workflows-secret'
echo '  Group Id:       <none>'
echo '  Redirect URL:   https://argo.fridge.internal/oauth2/callback'
echo
echo 'Also add the following entries to the /etc/hosts file of the host machine'
echo '** Note that these URLs should be configured in the corresponing Pulumi K3s stack'
echo 'The Argo URL is also used for OIDC redirect after Dex authenticates the user'
echo
echo $HOST_IP ' argo.fridge.internal'
echo $HOST_IP ' minio.fridge.internal'
echo $HOST_IP ' harbor.fridge.internal'
