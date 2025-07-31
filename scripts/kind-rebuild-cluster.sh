#!/bin/bash

# check is cluster exists
if kind get clusters | grep -q fridge; then
  echo "Cluster 'fridge' already exists. Rebuilding..."
  kind delete cluster --name fridge
else
  echo "Creating new cluster 'fridge'..."
fi
kind create cluster --name fridge --config /workspace/.devcontainer/kind-config.yaml
kind get kubeconfig --name fridge > /home/vscode/.kube/config
# fix kubeconfig to use the correct server address
export KUBE_API_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' fridge-control-plane)
export KUBE_API_ADDRESS="https://$KUBE_API_IP:6443"
yq -i '.clusters[0].cluster.server = strenv(KUBE_API_ADDRESS)' /home/vscode/.kube/config
# allow the devcontainer to access the cluster network
#check if the fridge-devcontainer is connected to the kind network
if [ $(docker inspect -f '{{json .NetworkSettings.Networks}}' fridge-devcontainer | jq '. | has("kind")') == "false" ]; then
  echo "Connecting fridge-devcontainer to kind network..."
  docker network connect kind fridge-devcontainer
else
  echo "fridge-devcontainer is already connected to kind network."
fi

# install cilium
if ! kubectl get pods -n kube-system | grep -q cilium; then
  echo "Installing Cilium..."
  /workspace/scripts/Install-Cillium.sh
else
  echo "Cilium is already installed."
fi