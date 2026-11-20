from enum import Enum, unique


@unique
class K8sEnvironment(Enum):
    AKS = "AKS"
    DAWN = "Dawn"
    K3S = "K3s"
    ZENITH = "Zenith"


@unique
class PodSecurityStandard(Enum):
    RESTRICTED = {"pod-security.kubernetes.io/enforce": "restricted"}
    PRIVILEGED = {"pod-security.kubernetes.io/enforce": "privileged"}


@unique
class TlsEnvironment(Enum):
    STAGING = "staging"
    PRODUCTION = "production"
    DEVELOPMENT = "development"


tls_issuer_names = {
    TlsEnvironment.STAGING: "letsencrypt-staging",
    TlsEnvironment.PRODUCTION: "letsencrypt-prod",
    TlsEnvironment.DEVELOPMENT: "dev-issuer",
}


class SoftwareVersion(Enum):
    # renovate: datasource=helm depName=gpu-operator-charts registryUrl=https://rocm.github.io/gpu-operator
    AMD_GPU_OPERATOR = "1.5.1"

    # renovate: datasource=helm depName=argo-workflows registryUrl=https://argoproj.github.io/argo-helm
    ARGO_WORKFLOWS = "2.0.6"  # Corresponds to Argo Workflows v4.1.3

    # renovate: datasource=helm depName=cert-manager registryUrl=https://charts.jetstack.io
    CERT_MANAGER = "1.21.2"

    # renovate: datasource=docker depName=curlimages/curl
    CURL = "8.22.0"

    # renovate: datasource=docker depName=ghcr.io/alan-turing-institute/fridge
    FRIDGE_API = "0.9.0"

    # renovate: datasource=docker depName=haproxy
    HAPROXY = "3.4.6"

    # renovate: datasource=helm depName=intel-device-plugins-operator registryUrl=https://intel.github.io/helm-charts
    INTEL_GPU_OPERATOR = "0.35.0"

    # renovate: datasource=helm depName=longhorn registryUrl=https://charts.longhorn.io
    LONGHORN = "1.9.0"

    # renovate: datasource=helm depName=node-feature-discovery registryUrl=https://kubernetes-sigs.github.io/node-feature-discovery/charts
    NODE_FEATURE_DISCOVERY = "0.18.3"

    # renovate: datasource=helm depName=seaweedfs registryUrl=https://seaweedfs.github.io/seaweedfs/helm
    SEAWEEDFS = "4.51.0"

    # renovate: datasource=helm depName=trust-manager registryUrl=https://charts.jetstack.io
    TRUST_MANAGER = "0.25.0"
