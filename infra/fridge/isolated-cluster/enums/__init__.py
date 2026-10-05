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


class SoftwareVersion(Enum):
    ARGO_WORKFLOWS = "2.0.6"  # Corresponds to Argo Workflows v4.1.3
    CERT_MANAGER = "1.17.1"
    CURL = "8.22.0"
    FRIDGE_API = "0.7.0"
    HAPROXY = "3.4.6"
    INTEL_GPU_OPERATOR = "0.35.0"
    LONGHORN = "1.9.0"
    NODE_FEATURE_DISCOVERY = "0.18.3"
    SEAWEEDFS = "4.47.0"
    TRUST_MANAGER = "0.21.1"
