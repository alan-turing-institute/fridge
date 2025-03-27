# Workflow based design

Once the cluster is set up, we can start to deploy the workflow based components. To set up the workflow based design, we will need to deploy the following components:

- Longhorn
- Ingress-Nginx controller
- Cert-manager
- MinIO
- Argo Workflows

Note that the following instructions are for a development environment, and will undergo further changes.

Some elements are currently set up inconsistently, reflecting the learning process. Some parts are currently missing. For example, no network policies are in place, and MinIO is not set up to use TLS internally.

## Longhorn

First, deploy Longhorn to manage the provision of block storage on the cluster.

```console
kubectl apply -f https://raw.githubusercontent.com/longhorn/longhorn/v1.8.1/deploy/longhorn.yaml
```

Next, create a storage class for Longhorn. There is a default storage class - `longhorn` - but there are some tweaks that can make it a little easier to use. The following is an example of a custom storage class that uses the Longhorn provisioner:

```yaml
kind: StorageClass
apiVersion: storage.k8s.io/v1
metadata:
  name: longhorn-storage
provisioner: driver.longhorn.io
allowVolumeExpansion: true
reclaimPolicy: Delete
volumeBindingMode: Immediate
parameters:
  numberOfReplicas: "2"
  staleReplicaTimeout: "30"
  fsType: "ext4"
  dataLocality: "best-effort"
```

This formats the volume with the `ext4` filesystem, and sets the number of replicas to `2` rather than the default of `3`. In addition, it sets the data locality to `best-effort`, which means that Longhorn will try to keep a replica of the volume on the same node as the pod that is using it.

To apply this yaml file, run the following command:

```console
kubectl apply -f common/longhorn-storage-class.yaml
```

Longhorn can now be used to provision volumes for use by the rest of the system.

## Deploy an Ingress Controller

Both MinIO and Argo Workflows will need to be accessed from outside the cluster, so we need to deploy an Ingress controller to route traffic to the correct services.

We will use the Nginx Ingress controller. An alternative would be Traefik.

Confusingly, there are two different Nginx Ingress controllers available for Kubernetes. The one we will use is the one provided by the Kubernetes project - `ingress-nginx`, which is the one that is most commonly used. The other - `nginx-ingress` - is provided by Nginx Inc.

As per the official instructions, the `ingress-nginx` controller can be deployed using the following command:

```console
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/cloud/deploy.yaml
```

This deploys the `ingress-nginx` controller to the `ingress-nginx` namespace.

When setting up Ingress resources later, we can specify the class of the Ingress controller to be used for that Ingress:

```yaml
ingressClassName: nginx
```

The Ingress controller will be given a public IP address by Azure. Point a DNS record at this IP address to make it easier to access the services.

The easiest way to do that for testing is to go to the Azure portal and find the public IP address of the Ingress controller. Look in the *actual* resource group for the cluster (<MC_resource-group_k8s-service_region>), and find the public IP address associated with the `ingress-nginx-controller` service. It will be in the format `kubernetes-<some-random-string>`. Select it, then go to the `Settings > Configuration` menu. Give the IP address a DNS name label - (e.g. 'dshstuff') - and save the changes. The DNS name will be in the format `<label>.<region>.cloudapp.azure.com`.

The next step is to set up TLS certificate issuers for the Ingress controller.

## TLS Certificates

To secure the Ingress controller, we need to provide TLS certificates. This can be done using [cert-manager](https://cert-manager.io/docs/installation/helm/).

```console
helm repo add jetstack https://charts.jetstack.io --force-update
```

To create the `cert-manager` namespace and install the `cert-manager` Helm chart, run the following command:

```console
helm install \
  cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --version v1.17.0 \
  --set crds.enabled=true
```

Once this is set-up, we can create a `ClusterIssuer` resource to request a certificate from Let's Encrypt.

The following is a `ClusterIssuer` that requests a certificate from the Let's Encrypt staging server for testing purposes.

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-staging
spec:
  acme:
    # The ACME server URL
    server: https://acme-staging-v02.api.letsencrypt.org/directory
    # Email address used for ACME registration
    email: your_email@example.com
    # Name of a secret used to store the ACME account private key
    privateKeySecretRef:
      name: letsencrypt-staging
    # Enable the HTTP-01 challenge provider
    solvers:
      - http01:
          ingress:
            ingressClassName: nginx
```

A `yaml` file to create cluster issuers for both staging and production certificates is included in the `common` directory. Apply this file to the cluster:

```console
apply -f common/letsencrypt-cluster-issuer.yaml
```

To use the issuers, add an annotation when creating the Ingress resources. E.g. to request a staging certificate, use:

```yaml
cert-manager.io/issuer: "letsencrypt-staging"
```

## MinIO

Argo Workflows is mostly designed around using S3 compatible storage to store its artifacts.

Minio provides an S3 compatible object storage system, with web-based access to the stored objects. This makes it a nice companion to Argo Workflows, in that it gives a nice easy way to upload (like scripts) and download artifacts (like graphs or other outputs).

Note that this is not the only way to provide storage for use with Argo Workflows. For example, you could use Azure Blob Storage, Google Cloud Storage, or any S3 compatible storage system. However, it is most cloud-agnostic to use an S3 compatible storage system within k8s.

We deploy MinIO in two steps. First we'll use the Helm chart for Minio to deploy its `operator` to the cluster.

The `minio-operator` will manage the deployment of MinIO instances in the cluster.

```console
helm repo add minio-operator https://operator.min.io
helm install \
  --namespace minio-operator \
  --create-namespace \
  minio-operator minio-operator/operator
```

Next we'll deploy a MinIO instance using its `tenant` Helm chart. We'll deploy it in a namespace called `argo-artifacts`.

Some custom values need to be set for this to work for our purposes. A values file is included in the `workflow-based` directory with some suggested defaults, but some additional fields need to be set.

The `features:` field needs to be configured with the domains being used. For example, I am hosting on `dshkubetest.uksouth.cloudapp.azure.com` with `minio` as a subpath. I need to set the `console` and `minio` domains to the following:

```yaml
features:
    bucketDNS: false
    domains:
      console: dshkubetest.uksouth.cloudapp.azure.com/minio/
      minio:
        - dshkubetest.uksouth.cloudapp.azure.com/minio/api/
        - minio.argo-artifacts.svc.cluster.local
    enableSFTP: false
```

The `console` domain is the web-based interface for MinIO, and the `minio` domain is the endpoint for the S3 API. I have found that these need to be set for the MinIO instance to work correctly.

The final section, `ExtraResources` creates a configuration file, and a secret containing the access key and secret key for the MinIO instance. This should be used to said the primary admin username and password for the MinIO instance. The `MINIO_BROWSER_REDIRECT_URL` should be set to the `console` domain as above. Note this is again only necessary if MinIO is hosted on a subpath.

The values file could also be used to set up the ingress for MinIO, but for now I do this manually.

Also of note, here I disable TLS for the MinIO instance. This is for simpler interfacing with Argo Workflows, which does not trust the self-signed certificates that MinIO can automatically generate. This can be addressed for production use.

When the file is ready, deploy the MinIO tenant:

```console
helm install \
--namespace argo-artifacts \
--create-namespace \
--values minio-tenant-values.yaml \
argo-artifacts minio-operator/tenant
```

Follow this up with an Ingress resource to route traffic to the MinIO instance:

```console
kubectl apply -f common/minio-tenant-ingress.yaml
```

Note that this we have not set up a TLS for this Ingress resourse, as the Ingress for Argo Workflows will handle the TLS certificate for the domain.

## Argo Workflow Setup

We'll use the Argo Workflows Helm chart to deploy the Argo Workflows controller and the Argo Workflows UI.

The suggested values file for the Argo Workflows Helm chart is `values-argo-workflows.yaml`. Some values need to be set in this file to make it work with the rest of the system.

To use SSO, you will need to set up an OIDC provider. You will need an Entra Tenant, and will need to set up an application on the Tenant to provide the necessary client ID and client secret.

```console
helm install argo-test argo/argo-workflows -f values-argo-workflows.yaml
```
