from enum import Enum, unique


@unique
class K8sEnvironment(Enum):
    AKS = "AKS"
    DAWN = "Dawn"
    K3S = "K3s"


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
    CERT_MANAGER = "1.19.4"
    CURL_JQ = "latest"
    HARBOR = "1.17.1"
    INGRESS_NGINX = "4.13.2"
    LONGHORN = "1.9.0"
    OPENSSH_SERVER = "version-10.2_p1-r0"
