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


@unique
class SoftwareVersion(Enum):
    CERT_MANAGER = "1.17.1"
    TRUST_MANAGER = "0.21.1"
