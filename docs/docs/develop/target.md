# Add a New Target

FRIDGE is deployed to a Kubernetes (k8s) cluster that must meet certain requirements

- Cilium Container network Interface CNI # for network policy enforcement
- Bring Your Own Key (BYOK) CSI Container Storage Interface

## Define a new K8s environment

The targets are defined in an Enum object in `infra/fridge/access_cluster/enums/__init__.py`.
These environments are used in flow control to make target specific changes.
Add your target to the Enum like the examples here

```python
{%
    include "../../../infra/fridge/access_cluster/enums/__init__.py"
    start="# START env enum"
    end="# END"
%}
```

## Storage Class

FRIDGE needs storage to support its functions.
This storage is presented via a [Storage Class](https://kubernetes.io/docs/concepts/storage/storage-classes/).
Ideally this needs to support passing a key to encrypt volumes.
This depends on the K8s implementations having a [CSI](https://kubernetes.io/docs/concepts/storage/volumes/#csi) that supports this.
If your K8s implementation does not have a CSI capable of this, you can instead use Longhorn.

Storage classes used by FRIDGE are defined, for each K8s environment, in `infra/fridge/access_cluster/components/storage_classes.py`
Each target must define,

`storage_class`
:   Storage class object for sensitive data.
    Encrypted with a deployer-provider key or by Longhorn.

`standard_storage_name`
:   String giving the name of a storage class for non-sensitive data.

`standard_supports_rwm`
:   Boolean indicating whether the storage class named `standard_storage_name` support [`ReadWriteMany`](https://kubernetes.io/docs/concepts/storage/persistent-volumes/#access-modes).

```python
{%
    include "../../../infra/fridge/access_cluster/components/storage_classes.py"
    start="# START storage classes"
    end="# END"
%}
```

## Network Policies

Some K8s providers might require some tweaks to the Cilium network policies.
These are collected, similarly to storage classes in `infra/fridge/access_cluster/components/network_policies.py`.
For example with AKS,

```python
{%
    include "../../../infra/fridge/access_cluster/components/network_policies.py"
    start="# START network policies"
    end="# END"
%}
```

Here the policy manifests are defined in `.access_cluster/k8s/cilium/aks.yaml`.

## Service Changes

You may also need to deploy extra services, or you may want to avoid replacing services which are already deployed.
This may be most convenient to do in `infra/fridge/access_cluster/__main__.py`.

For example, the Hubble interface for Cilium is not provisioned automatically on AKS, so it is deployed here,

```python
{%
    include "../../../infra/fridge/access_cluster/__main__.py"
    start="# START hubble"
    end="# END"
%}
```
