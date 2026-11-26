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

# Class for software versions - e.g. for helm charts and container images
# where possible, these should be set to specific versions rather than "latest" to ensure reproducibility,
# and protect against breaking changes.
# But in some cases (e.g. curl-jq) no numbered version tags are available.
@unique
class SoftwareVersion(Enum):
    # renovate: datasource=helm depName=cert-manager registryUrl=https://charts.jetstack.io
    CERT_MANAGER = "1.21.2"
    # NOTE: renovate does not track images marked as "latest"
    CURL_JQ = "latest"
    # renovate: datasource=docker depName=haproxy
    HAPROXY = "3.4.8"
    # renovate: datasource=helm depName=harbor registryUrl=https://helm.goharbor.io
    HARBOR = "1.19.2"
    # renovate: datasource=helm depName=ingress-nginx registryUrl=https://kubernetes.github.io/ingress-nginx
    INGRESS_NGINX = "4.15.1"
    # renovate: datasource=helm depName=kube-prometheus-stack registryUrl=https://prometheus-community.github.io/helm-charts
    KUBE_PROMETHEUS_STACK = "92.17.0"
    # renovate: datasource=helm depName=longhorn registryUrl=https://charts.longhorn.io
    LONGHORN = "1.9.0"
    # renovate: datasource=docker depName=netbirdio/netbird
    NETBIRD = "0.83.2"
