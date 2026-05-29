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
    INTEL_GPU_OPERATOR = "0.35.0"
    MINIO_MC = "RELEASE.2025-08-13T08-35-41Z"
    MINIO_OPERATOR = "7.1.1"
    MINIO_TENANT = "7.1.1"
    NODE_FEATURE_DISCOVERY = "0.18.3"
    TRUST_MANAGER = "0.21.1"
