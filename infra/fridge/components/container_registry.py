import pulumi
from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.core.v1 import Namespace
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs, RepositoryOptsArgs
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs
from pulumi_kubernetes.networking.v1 import Ingress

from .storage_classes import StorageClasses

from enums import PodSecurityStandard, TlsEnvironment, tls_issuer_names


class ContainerRegistryArgs:
    def __init__(
        self,
        config: pulumi.config.Config,
        storage_classes: StorageClasses,
        tls_environment: TlsEnvironment,
    ) -> None:
        self.config = config
        self.tls_environment = tls_environment
        self.storage_classes = storage_classes


class ContainerRegistry(ComponentResource):
    def __init__(
        self, name: str, args: ContainerRegistryArgs, opts: ResourceOptions = None
    ):
        super().__init__("fridge:ContainerRegistry", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        harbor_ns = Namespace(
            "harbor-ns",
            metadata=ObjectMetaArgs(
                name="harbor",
                labels={} | PodSecurityStandard.RESTRICTED.value,
            ),
            opts=child_opts,
        )

        harbor_fqdn = ".".join(
            (
                args.config.require("harbor_fqdn_prefix"),
                args.config.require("base_fqdn"),
            )
        )

        harbor_external_url = f"https://{harbor_fqdn}"

        harbor = Release(
            "harbor",
            ReleaseArgs(
                chart="harbor",
                namespace="harbor",
                version="1.17.1",
                repository_opts=RepositoryOptsArgs(
                    repo="https://helm.goharbor.io",
                ),
                values={
                    "expose": {
                        "clusterIP": {
                            "staticClusterIP": args.config.require("harbor_ip"),
                        },
                        "type": "clusterIP",
                        "tls": {
                            "enabled": False,
                            "certSource": "none",
                        },
                    },
                    "externalURL": harbor_external_url,
                    "harborAdminPassword": args.config.require_secret(
                        "harbor_admin_password"
                    ),
                    "persistence": {
                        "persistentVolumeClaim": {
                            "registry": {
                                "storageClass": args.storage_classes.rwm_class_name,
                                "accessMode": "ReadWriteMany",
                            },
                            "jobservice": {
                                "jobLog": {
                                    "storageClass": args.storage_classes.rwm_class_name,
                                    "accessMode": "ReadWriteMany",
                                }
                            },
                        },
                    },
                },
            ),
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[harbor_ns]),
            ),
        )

        harbor_ingress = Ingress(
            "harbor-ingress",
            metadata=ObjectMetaArgs(
                name="harbor-ingress",
                namespace=harbor_ns.metadata.name,
                annotations={
                    "nginx.ingress.kubernetes.io/force-ssl-redirect": "true",
                    "nginx.ingress.kubernetes.io/proxy-body-size": "0",
                    "cert-manager.io/cluster-issuer": tls_issuer_names[
                        args.tls_environment
                    ],
                },
            ),
            spec={
                "ingress_class_name": "nginx",
                "tls": [
                    {
                        "hosts": [
                            harbor_fqdn,
                        ],
                        "secret_name": "harbor-ingress-tls",
                    }
                ],
                "rules": [
                    {
                        "host": harbor_fqdn,
                        "http": {
                            "paths": [
                                {
                                    "path": "/",
                                    "path_type": "Prefix",
                                    "backend": {
                                        "service": {
                                            "name": "harbor",
                                            "port": {
                                                "number": 80,
                                            },
                                        }
                                    },
                                }
                            ]
                        },
                    }
                ],
            },
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(
                    depends_on=[
                        harbor,
                    ]
                ),
            ),
        )

        self.harbor_fqdn = harbor_fqdn
        self.harbor_external_url = harbor_external_url

        self.register_outputs(
            {
                "harbor": harbor,
                "harbor_ingress": harbor_ingress,
                "harbor_ns": harbor_ns,
            }
        )
