import pulumi

from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.apiextensions import CustomResource
from pulumi_kubernetes.core.v1 import Namespace
from pulumi_kubernetes.helm.v3 import Release
from pulumi_kubernetes.helm.v4 import Chart, RepositoryOptsArgs
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs

from enums import K8sEnvironment, PodSecurityStandard


class CertManagerArgs:
    def __init__(
        self,
        config: pulumi.config.Config,
        k8s_environment: K8sEnvironment,
    ):
        self.config = config
        self.k8s_environment = k8s_environment


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
                        "global": {
                            "priorityClass": "system-cluster-critical",
                        },
                        "automountServiceAccountToken": False,
                        "serviceAccount": {
                            "automountServiceAccountToken": False,
                        },
                        "volumes": [
                            {
                                "name": "serviceaccount-token",
                                "projected": {
                                    "defaultMode": 0o444,
                                    "sources": [
                                        {
                                            "serviceAccountToken": {
                                                "expirationSeconds": 3607,
                                                "path": "token",
                                            }
                                        },
                                        {
                                            "configMap": {
                                                "name": "kube-root-ca.crt",
                                                "items": [
                                                    {"key": "ca.crt", "path": "ca.crt"}
                                                ],
                                            }
                                        },
                                        {
                                            "downwardAPI": {
                                                "items": [
                                                    {
                                                        "path": "namespace",
                                                        "fieldRef": {
                                                            "apiVersion": "v1",
                                                            "fieldPath": "metadata.namespace",
                                                        },
                                                    }
                                                ]
                                            }
                                        },
                                    ],
                                },
                            }
                        ],
                        "volumeMounts": [
                            {
                                "mountPath": "/var/run/secrets/kubernetes.io/serviceaccount",
                                "name": "serviceaccount-token",
                                "readOnly": True,
                            }
                        ],
                        "webhook": {
                            "replicaCount": 2,
                            "automountServiceAccountToken": False,
                            "serviceAccount": {
                                "automountServiceAccountToken": False,
                            },
                            "volumes": [
                                {
                                    "name": "serviceaccount-token",
                                    "projected": {
                                        "defaultMode": 0o444,
                                        "sources": [
                                            {
                                                "serviceAccountToken": {
                                                    "expirationSeconds": 3607,
                                                    "path": "token",
                                                }
                                            },
                                            {
                                                "configMap": {
                                                    "name": "kube-root-ca.crt",
                                                    "items": [
                                                        {
                                                            "key": "ca.crt",
                                                            "path": "ca.crt",
                                                        }
                                                    ],
                                                }
                                            },
                                            {
                                                "downwardAPI": {
                                                    "items": [
                                                        {
                                                            "path": "namespace",
                                                            "fieldRef": {
                                                                "apiVersion": "v1",
                                                                "fieldPath": "metadata.namespace",
                                                            },
                                                        }
                                                    ]
                                                }
                                            },
                                        ],
                                    },
                                }
                            ],
                            "volumeMounts": [
                                {
                                    "mountPath": "/var/run/secrets/kubernetes.io/serviceaccount",
                                    "name": "serviceaccount-token",
                                    "readOnly": True,
                                }
                            ],
                        },
                        "cainjector": {
                            "replicaCount": 2,
                            "automountServiceAccountToken": False,
                            "serviceAccount": {
                                "automountServiceAccountToken": False,
                            },
                            "volumes": [
                                {
                                    "name": "serviceaccount-token",
                                    "projected": {
                                        "defaultMode": 0o444,
                                        "sources": [
                                            {
                                                "serviceAccountToken": {
                                                    "expirationSeconds": 3607,
                                                    "path": "token",
                                                }
                                            },
                                            {
                                                "configMap": {
                                                    "name": "kube-root-ca.crt",
                                                    "items": [
                                                        {
                                                            "key": "ca.crt",
                                                            "path": "ca.crt",
                                                        }
                                                    ],
                                                }
                                            },
                                            {
                                                "downwardAPI": {
                                                    "items": [
                                                        {
                                                            "path": "namespace",
                                                            "fieldRef": {
                                                                "apiVersion": "v1",
                                                                "fieldPath": "metadata.namespace",
                                                            },
                                                        }
                                                    ]
                                                }
                                            },
                                        ],
                                    },
                                }
                            ],
                            "volumeMounts": [
                                {
                                    "mountPath": "/var/run/secrets/kubernetes.io/serviceaccount",
                                    "name": "serviceaccount-token",
                                    "readOnly": True,
                                }
                            ],
                        },
                    },
                    opts=ResourceOptions.merge(
                        child_opts,
                        ResourceOptions(
                            depends_on=[cert_manager_ns],
                        ),
                    ),
                )

        # Create ClusterIssuers
        issuer_outputs = {}
        # Always create a self-signed issuer and cert for use in development and for internal services
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

        # Add trust-manager
        self.trust_manager = Release(
            "trust-manager",
            namespace=cert_manager_ns.metadata.name,
            chart="trust-manager",
            version="0.21.1",
            repository_opts=RepositoryOptsArgs(
                repo="https://charts.jetstack.io",
            ),
            values={
                "secretTargets": {
                    "enabled": True,
                    "authorizedSecrets": [
                        "trusted-certificates",
                        "operator-ca-tls-argo-artifacts",
                    ],
                },
                "resources": {
                    "requests": {
                        "cpu": "100m",
                        "memory": "128Mi",
                    },
                },
            },
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[cert_manager]),
            ),
        )

        # Create a trust bundle with the dev certificate as a source
        # Allows mirroring of the cert into tagged namespaces to be used by internal services
        self.trust_bundle = CustomResource(
            "trust-bundle",
            api_version="trust.cert-manager.io/v1alpha1",
            kind="Bundle",
            metadata=ObjectMetaArgs(
                name="trusted-certificates",
            ),
            spec={
                "sources": [
                    {"useDefaultCAs": True},
                    {"secret": {"name": "dev-certificate", "key": "ca.crt"}},
                ],
                "target": {
                    "secret": {
                        "key": "ca-certificates.crt",
                    },
                    "namespaceSelector": {
                        "matchLabels": {
                            "tls-trust-bundle": "enabled",
                        }
                    },
                },
            },
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[self.trust_manager]),
            ),
        )

        self.register_outputs(
            {
                "cert-manager": cert_manager,
                "cert-manager-ns": cert_manager_ns,
                **issuer_outputs,
            }
        )
