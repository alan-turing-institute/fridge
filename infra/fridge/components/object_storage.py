import pulumi
from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.core.v1 import Namespace
from pulumi_kubernetes.helm.v3 import Chart, RepositoryOptsArgs
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs

from enums import K8sEnvironment, PodSecurityStandard


class ObjectStorageArgs:
    def __init__(self, k8s_environment: K8sEnvironment) -> None:
        self.k8s_environment = k8s_environment


class ObjectStorage(ComponentResource):
    def __init__(
        self, name: str, args: ObjectStorageArgs, opts: ResourceOptions | None = None
    ) -> None:
        super().__init__("fridge:k8s:ObjectStorage", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        minio_operator_ns = Namespace(
            "minio-operator-ns",
            metadata=ObjectMetaArgs(
                name="minio-operator",
                labels={} | PodSecurityStandard.RESTRICTED.value,
            ),
        )

        minio_tenant_ns = Namespace(
            "minio-tenant-ns",
            metadata=ObjectMetaArgs(
                name="argo-artifacts",
                labels={} | PodSecurityStandard.RESTRICTED.value,
            ),
        )

        minio_operator = Chart(
            "minio-operator",
            namespace=minio_operator_ns.metadata.name,
            chart="operator",
            repository_opts=RepositoryOptsArgs(
                repo="https://operator.min.io",
            ),
            version="7.1.1",
            opts=ResourceOptions(
                depends_on=[minio_operator_ns],
            ),
        )

        minio_fqdn = ".".join(
            (
                config.require("minio_fqdn_prefix"),
                config.require("base_fqdn"),
            )
        )
        pulumi.export("minio_fqdn", minio_fqdn)

        minio_config_env = Output.format(
            (
                "export MINIO_BROWSER_REDIRECT_URL=https://{0}\n"
                "export MINIO_SERVER_URL=http://minio.argo-artifacts.svc.cluster.local\n"
                "export MINIO_ROOT_USER={1}\n"
                "export MINIO_ROOT_PASSWORD={2}"
            ),
            minio_fqdn,
            config.require_secret("minio_root_user"),
            config.require_secret("minio_root_password"),
        )

        minio_env_secret = Secret(
            "minio-env-secret",
            metadata=ObjectMetaArgs(
                name="argo-artifacts-env-configuration",
                namespace=minio_tenant_ns.metadata.name,
            ),
            type="Opaque",
            string_data={
                "config.env": minio_config_env,
            },
            opts=ResourceOptions(
                depends_on=[minio_tenant_ns],
            ),
        )

        minio_tenant = Chart(
            "minio-tenant",
            namespace=minio_tenant_ns.metadata.name,
            chart="tenant",
            name="argo-artifacts",
            version="7.1.1",
            repository_opts=RepositoryOptsArgs(
                repo="https://operator.min.io",
            ),
            values={
                "tenant": {
                    "name": "argo-artifacts",
                    "buckets": [
                        {"name": "argo-artifacts"},
                    ],
                    "certificate": {
                        "requestAutoCert": "false",
                    },
                    "configuration": {
                        "name": "argo-artifacts-env-configuration",
                    },
                    "configSecret": {
                        "name": "argo-artifacts-env-configuration",
                        "accessKey": None,
                        "secretKey": None,
                        "existingSecret": "true",
                    },
                    "features": {
                        "domains": {
                            "console": minio_fqdn,
                            "minio": [
                                Output.concat(minio_fqdn, "/api"),
                                "minio.argo-artifacts.svc.cluster.local",
                            ],
                        }
                    },
                    "pools": [
                        {
                            "servers": 1,
                            "name": "argo-artifacts-pool-0",
                            "size": config.require("minio_pool_size"),
                            "volumesPerServer": 1,
                            "storageClassName": storage_classes.encrypted_storage_class.metadata.name,
                            "containerSecurityContext": {
                                "runAsUser": 1000,
                                "runAsGroup": 1000,
                                "runAsNonRoot": True,
                                "allowPrivilegeEscalation": False,
                                "capabilities": {"drop": ["ALL"]},
                                "seccompProfile": {
                                    "type": "RuntimeDefault",
                                },
                            },
                        },
                    ],
                },
            },
            opts=ResourceOptions(
                depends_on=[
                    storage_classes,
                    minio_env_secret,
                    minio_operator,
                    minio_tenant_ns,
                ],
            ),
        )

        minio_ingress = Ingress(
            "minio-ingress",
            metadata=ObjectMetaArgs(
                name="minio-ingress",
                namespace=minio_tenant_ns.metadata.name,
                annotations={
                    "nginx.ingress.kubernetes.io/proxy-body-size": "0",
                    "nginx.ingress.kubernetes.io/force-ssl-redirect": "true",
                    "cert-manager.io/cluster-issuer": tls_issuer_names[tls_environment],
                },
            ),
            spec={
                "ingress_class_name": "nginx",
                "tls": [
                    {
                        "hosts": [
                            minio_fqdn,
                        ],
                        "secret_name": "argo-artifacts-tls",
                    }
                ],
                "rules": [
                    {
                        "host": minio_fqdn,
                        "http": {
                            "paths": [
                                {
                                    "path": "/",
                                    "path_type": "Prefix",
                                    "backend": {
                                        "service": {
                                            "name": "argo-artifacts-console",
                                            "port": {
                                                "number": 9090,
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
                depends_on=[minio_tenant],
            ),
        )
