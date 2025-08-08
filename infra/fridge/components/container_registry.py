import pulumi
from pulumi import ComponentResource, ResourceOptions

from .storage_classes import StorageClasses

from enums import PodSecurityStandard, TlsEnvironment, tls_issuer_names


class ContainerRegistryArgs:
    def __init__(self, config: Pulumi.Config, tls_environment: TlsEnvironment):
        self.config = config
        self.tls_environment = tls_environment


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
        )

        harbor_fqdn = ".".join(
            (
                config.require("harbor_fqdn_prefix"),
                config.require("base_fqdn"),
            )
        )

        f"{config.require('harbor_fqdn_prefix')}.{config.require('base_fqdn')}"
        pulumi.export("harbor_fqdn", harbor_fqdn)
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
                            "staticClusterIP": config.require("harbor_ip"),
                        },
                        "type": "clusterIP",
                        "tls": {
                            "enabled": False,
                            "certSource": "none",
                        },
                    },
                    "externalURL": harbor_external_url,
                    "harborAdminPassword": config.require_secret(
                        "harbor_admin_password"
                    ),
                    "persistence": {
                        "persistentVolumeClaim": {
                            "registry": {
                                "storageClass": storage_classes.rwm_class_name,
                                "accessMode": "ReadWriteMany",
                            },
                            "jobservice": {
                                "jobLog": {
                                    "storageClass": storage_classes.rwm_class_name,
                                    "accessMode": "ReadWriteMany",
                                }
                            },
                        },
                    },
                },
            ),
            opts=ResourceOptions(
                depends_on=[harbor_ns, storage_classes],
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
                    "cert-manager.io/cluster-issuer": tls_issuer_names[tls_environment],
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
            opts=ResourceOptions(
                depends_on=[harbor],
            ),
        )
