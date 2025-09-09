from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.core.v1 import Namespace
from pulumi_kubernetes.helm.v3 import Release
from pulumi_kubernetes.helm.v4 import Chart, RepositoryOptsArgs
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs

from enums import K8sEnvironment, PodSecurityStandard, TlsEnvironment


class CertManagerArgs:
    def __init__(
        self, k8s_environment: K8sEnvironment, tls_environment: TlsEnvironment
    ):
        self.k8s_environment = k8s_environment
        self.tls_environment = tls_environment


class CertManager(ComponentResource):
    def __init__(self, name: str, args: CertManagerArgs, opts: ResourceOptions = None):
        super().__init__("fridge:k8s:CertManager", name, {}, opts)

        k8s_environment = args.k8s_environment

        match k8s_environment:
            case K8sEnvironment.AKS | K8sEnvironment.K3S:
                # AKS specific configuration
                # CertManager (TLS automation)
                cert_manager_ns = Namespace(
                    "cert-manager-ns",
                    metadata=ObjectMetaArgs(
                        name="cert-manager",
                        labels={} | PodSecurityStandard.RESTRICTED.value,
                    ),
                )

                cert_manager = Chart(
                    "cert-manager",
                    namespace=cert_manager_ns.metadata.name,
                    chart="cert-manager",
                    version="1.17.1",
                    repository_opts=RepositoryOptsArgs(
                        repo="https://charts.jetstack.io",
                    ),
                    values={
                        "crds": {"enabled": True},
                        "extraArgs": [
                            "--acme-http01-solver-nameservers=8.8.8.8:53,1.1.1.1:53"
                        ],
                    },
                    opts=ResourceOptions(
                        depends_on=[cert_manager_ns],
                    ),
                )
            case K8sEnvironment.DAWN:
                # Dawn specific configuration
                cert_manager_ns = Namespace.get("cert-manager-ns", "cert-manager")
                cert_manager = Release.get("cert-manager", "cert-manager")

        self.register_outputs(
            {
                "cert-manager": cert_manager,
                "cert-manager-ns": cert_manager_ns,
            }
        )
