.PHONY: *

ROOT_DIR_PATH := $(dir $(realpath $(lastword $(MAKEFILE_LIST))))
K3D_CLUSTER_NAME := "frigde"
DEV_KUBECONFIG_PATH := "$(ROOT_DIR_PATH)/kubeconfig.yaml"


k3d: k3d-cluster
	crd2pulumi --pythonPath=infra/k3d/crds --force  https://raw.githubusercontent.com/cilium/cilium/c90aed4c6479daf5df0aada14860af91f1b05b3f/pkg/k8s/apis/cilium.io/client/crds/v2/ciliumnetworkpolicies.yaml
	cd infra/k3d/ && ./venv/bin/pip install ./crds
	$(MAKE) k3d-up

k3d-up:
	cd infra/k3d && \
	 KUBECONFIG=$(DEV_KUBECONFIG_PATH) pulumi up

k3d-destroy:
	cd infra/k3d && \
	 KUBECONFIG=$(DEV_KUBECONFIG_PATH) pulumi down
	k3d cluster delete $(K3D_CLUSTER_NAME)

k3d-cluster:
	if ! k3d cluster list | grep -q $(K3D_CLUSTER_NAME); then \
	  k3d cluster create $(K3D_CLUSTER_NAME) \
	    --api-port 6550 \
	    --servers 1 \
	    --agents 0 \
		--k3s-arg="--flannel-backend=none@all:*" \
	    --k3s-arg="--disable=traefik@server:*" \
	    --k3s-arg="--disable-cloud-controller@server:*" \
	    --k3s-arg="--disable-helm-controller@server:*" \
	    --k3s-arg="--etcd-disable-snapshots@server:*" \
	    --volume "$${PWD}:/repo@all" \
	    --wait; \
	fi
	k3d kubeconfig get $(K3D_CLUSTER_NAME) > $(DEV_KUBECONFIG_PATH)
