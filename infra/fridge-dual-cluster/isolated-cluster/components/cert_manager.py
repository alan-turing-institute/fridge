import pulumi

from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.apiextensions import CustomResource
from pulumi_kubernetes.core.v1 import Namespace
from pulumi_kubernetes.helm.v3 import Release
from pulumi_kubernetes.helm.v4 import Chart, RepositoryOptsArgs
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs

from enums import K8sEnvironment, PodSecurityStandard, TlsEnvironment, tls_issuer_names


class CertManagerArgs:
    def __init__(
        self,
        config: pulumi.config.Config,
        k8s_environment: K8sEnvironment,
        tls_environment: TlsEnvironment,
    ):
        self.config = config
        self.k8s_environment = k8s_environment
        self.tls_environment = tls_environment


class CertManager(ComponentResource):
    def __init__(
        self, name: str, args: CertManagerArgs, opts: ResourceOptions | None = None
    ):
        super().__init__("fridge:k8s:CertManager", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        k8s_environment = args.k8s_environment

        match k8s_environment:
            case K8sEnvironment.AKS | K8sEnvironment.K3S | K8sEnvironment.DAWN:
                # AKS specific configuration
                # CertManager (TLS automation)
                cert_manager_ns = Namespace(
                    "cert-manager-ns",
                    metadata=ObjectMetaArgs(
                        name="cert-manager",
                        labels={} | PodSecurityStandard.RESTRICTED.value,
                    ),
                    opts=child_opts,
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
                    opts=ResourceOptions.merge(
                        child_opts,
                        ResourceOptions(
                            depends_on=[cert_manager_ns],
                        ),
                    ),
                )
            # case K8sEnvironment.DAWN:
            #     # Dawn specific configuration
            #     cert_manager_ns = Namespace.get("cert-manager-ns", "cert-manager")
            #     cert_manager = Release.get("cert-manager", "cert-manager")

        # Create ClusterIssuers
        issuer_outputs = {}
        # if we're using TLS development use a self-signed issuer for the certificate
        if args.tls_environment == TlsEnvironment.DEVELOPMENT:
            cert_manager_secretName = "dev-certificate"
            cert_manager_dev_issuer_self_signed = CustomResource(
                resource_name="cert-manager-dev-self-signed-issuer",
                api_version="cert-manager.io/v1",
                kind="ClusterIssuer",
                metadata=ObjectMetaArgs(
                    name="self-signed",
                ),
                spec={"selfSigned": {}},
                opts=ResourceOptions(depends_on=[cert_manager]),
            )
            cert_manager_dev_certificate = CustomResource(
                resource_name="cert-manager-dev-certificate",
                api_version="cert-manager.io/v1",
                kind="Certificate",
                metadata=ObjectMetaArgs(
                    name="dev-certificate",
                    namespace="cert-manager",
                ),
                spec={
                    "isCA": True,
                    "secretName": cert_manager_secretName,
                    "privateKey": {"algorithm": "ECDSA", "size": 256},
                    "issuerRef": {
                        "name": "self-signed",
                        "kind": "ClusterIssuer",
                        "group": "cert-manager.io",
                    },
                    "commonName": args.config.require("base_fqdn"),
                    "dnsNames": [
                        args.config.require("base_fqdn"),
                        f"*.{args.config.require('base_fqdn')}",
                    ],
                },
                opts=ResourceOptions.merge(
                    child_opts,
                    ResourceOptions(depends_on=[cert_manager_dev_issuer_self_signed]),
                ),
            )
            cert_manager_dev_issuer = CustomResource(
                resource_name="cert-manager-dev-issuer",
                api_version="cert-manager.io/v1",
                kind="ClusterIssuer",
                metadata=ObjectMetaArgs(
                    name="dev-issuer",
                    namespace="cert-manager",
                ),
                spec={"ca": {"secretName": cert_manager_secretName}},
                opts=ResourceOptions.merge(
                    child_opts,
                    ResourceOptions(depends_on=[cert_manager_dev_certificate]),
                ),
            )
            issuer_outputs = {
                "cert_manager_dev_issuer_self_signed": cert_manager_dev_issuer_self_signed,
                "cert_manager_dev_certificate": cert_manager_dev_certificate,
                "cert_manager_dev_issuer": cert_manager_dev_issuer,
            }
        else:
            cert_manager_issuers = CustomResource(
                "cert-manager-issuer",
                api_version="cert-manager.io/v1",
                kind="ClusterIssuer",
                metadata=ObjectMetaArgs(
                    name=tls_issuer_names[args.tls_environment],
                ),
                spec={
                    "acme": {
                        "email": args.config.require("lets_encrypt_email"),
                        "server": "https://acme-v02.api.letsencrypt.org/directory"
                        if args.tls_environment == TlsEnvironment.PRODUCTION
                        else "https://acme-staging-v02.api.letsencrypt.org/directory",
                        "privateKeySecretRef": {"name": "letsencrypt-private-key"},
                        "solvers": [
                            {
                                "http01": {
                                    "ingress": {"class": "nginx"},
                                }
                            }
                        ],
                    }
                },
                opts=ResourceOptions.merge(
                    child_opts, ResourceOptions(depends_on=[cert_manager])
                ),
            )
            issuer_outputs = {
                "cert_manager_issuers": cert_manager_issuers,
            }

        self.register_outputs(
            {
                "cert-manager": cert_manager,
                "cert-manager-ns": cert_manager_ns,
                **issuer_outputs,
            }
        )
