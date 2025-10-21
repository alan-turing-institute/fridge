FRIDGE is deployed to a kubernetes (k8s) cluster that must meet certain requirements
- Cilium Container network Interface CNI # for network policy enforcement
- Bring Your Own Key (BYOK) CSI Container Storage Interface
!# other requirements outside of K8s requirements not listed here unless required
!# code examples taken on 04/09/2025 from commit `dd60faff6f88a4e522332b0bb72e3f571c6de8d6`
# first: add a new k8s_enviroment enum
open `infra/fridge/enums/__init__.py`
update the file like the example below
```Python ln:4 title:infra/fridge/enums/__init__.py
@unique
class K8sEnvironment(Enum):
	AKS = "AKS"
	DAWN = "Dawn"
	K3S = "K3s"
	OKE = "OKE" #new addition
```
this is used later for making changes to how FRIDGE is deployed based on this value (also restricts to only valid options listed)

# Storage Class
FRIDGE of course needs storage to support it's functions, this storage is presented via a Storage Class this needs to support BYOK encryption for the volumes.

some k8s providers come with a CSI that supports this in which case `infra/fridge/components/storage_classes.py` needs to be updated to make use of this CSI

if your k8s provider doesn't have a CSI with BYOK encryption support then you can instead use longhorn and provide the worker nodes with the required disk for longhorn to make use of
```python ln:55 title:infra/fridge/components/storage_classes.py
case K8sEnvironment.DAWN:
	longhorn_ns = Namespace(
		"longhorn-system",
		metadata=ObjectMetaArgs(
			name="longhorn-system",
			labels={} | PodSecurityStandard.PRIVILEGED.value,
		),
		opts=child_opts,
	)

	longhorn = Release(
		"longhorn",
		namespace=longhorn_ns.metadata.name,
		chart="longhorn",version="1.9.0",
		repository_opts=RepositoryOptsArgs(
			repo="https://charts.longhorn.io",
		),
		# Add a toleration for the GPU node, to allow Longhorn to schedule pods/create volumes there
		values={
			"global": {
"""... cut short for space"""
```

# Network Policies
Some k8s providers might requires some tweaks to the cilium network policies Example Below
```Python ln:7 title:infra/fridge/components/network_policies.py
class NetworkPolicies(ComponentResource):
	def __init__(
		self, name: str, k8s_environment: K8sEnvironment,
		opts=ResourceOptions
	) -> None:
		super().__init__("fridge:k8s:NetworkPolicies", name, {}, opts)
		child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

		match k8s_environment:
			case K8sEnvironment.AKS:
				# AKS uses Konnectivity to mediate some API/webhook traffic, and uses a different external DNS server
				ConfigFile(
					"network_policy_aks",
					file="./k8s/cilium/aks.yaml",
					opts=child_opts,
				)
case K8sEnvironment.DAWN:
```
you can see it referances a manifest `infra/fridge/k8s/aks.yaml` that should be deployed to support Konnectivity, these are CiliumNetworkPolicy Manifests which enabled the needed connectivity

# Loadbalancer
to be able to access the FRIDGE API outside of the cluster a Load balancer is use (not a hard requirement NodePort could be used but isn't best practice)

most cloud providers have load balancer functionality, otherwise options like MetalLB, Kube-VIP, Cilium

these Load balancer IPs should only be accessible from the proxy node

# other changes
below are some examples of other changes to help further illustrate  how this can be done

###### base cilium install doesn't include Hubble UI
```python ln:40 title:infra/fridge/__main__.py
# Hubble UI
# Interface for Cilium
if k8s_environment == K8sEnvironment.AKS:
	hubble_ui = ConfigFile(
		"hubble-ui",
		file="./k8s/hubble/hubble_ui.yaml",
	)
```

###### add needed ingress nginx config
```python ln:49 title:infra/firdge/__main__.py
case K8sEnvironment.AKS | K8sEnvironment.K3S:
	# Ingress NGINX (ingress provider)
	ingress_nginx_ns = Namespace(
		"ingress-nginx-ns",
		metadata=ObjectMetaArgs(
			name="ingress-nginx",
			labels={} | PodSecurityStandard.RESTRICTED.value,
		),
	)

	ingress_nginx = ConfigFile(
		"ingress-nginx",
		file="https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.12.1/deploy/static/provider/cloud/deploy.yaml",
		opts=ResourceOptions(
			depends_on=[ingress_nginx_ns],
		),
	)
"""... other AKS specific config happens past this point
```
