import pulumi
from pulumi import ComponentResource, Output, ResourceOptions
from pulumi_kubernetes.core.v1 import Namespace, Secret
from pulumi_kubernetes.helm.v4 import Chart, RepositoryOptsArgs
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs
from pulumi_kubernetes.networking.v1 import (
    Ingress,
    IngressBackendArgs,
    IngressServiceBackendArgs,
    IngressSpecArgs,
    IngressRuleArgs,
    IngressTLSArgs,
)
from .storage_classes import StorageClasses

from enums import PodSecurityStandard, TlsEnvironment, tls_issuer_names


class ObjectStorageArgs:
    def __init__(
        self,
        config: pulumi.config.Config,
        storage_classes: StorageClasses,
        tls_environment: TlsEnvironment,
    ) -> None:
        self.config = config
        self.tls_environment = tls_environment
        self.storage_classes = storage_classes


class ObjectStorage(ComponentResource):
    def __init__(
        self, name: str, args: ObjectStorageArgs, opts: ResourceOptions | None = None
    ) -> None:
        super().__init__("fridge:ObjectStorage", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        self.minio_operator_ns = Namespace(
            "minio-operator-ns",
            metadata=ObjectMetaArgs(
                name="minio-operator",
                labels={} | PodSecurityStandard.RESTRICTED.value,
            ),
            opts=child_opts,
        )

        self.minio_tenant_ns = Namespace(
            "minio-tenant-ns",
            metadata=ObjectMetaArgs(
                name="argo-artifacts",
                labels={} | PodSecurityStandard.RESTRICTED.value,
            ),
            opts=child_opts,
        )

        self.minio_operator = Chart(
            "minio-operator",
            namespace=self.minio_operator_ns.metadata.name,
            chart="operator",
            repository_opts=RepositoryOptsArgs(
                repo="https://operator.min.io",
            ),
            version="7.1.1",
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[self.minio_operator_ns]),
            ),
        )

        self.minio_fqdn = ".".join(
            (
                args.config.require("minio_fqdn_prefix"),
                args.config.require("base_fqdn"),
            )
        )

        self.minio_cluster_url = pulumi.Output.concat(
            "minio.", self.minio_tenant_ns.metadata.name, ".svc.cluster.local"
        )

        minio_config_env = Output.format(
            (
                "export MINIO_BROWSER_REDIRECT_URL=https://{0}\n"
                "export MINIO_SERVER_URL=http://{1}\n"
                "export MINIO_ROOT_USER={2}\n"
                "export MINIO_ROOT_PASSWORD={3}"
            ),
            self.minio_fqdn,
            self.minio_cluster_url,
            args.config.require_secret("minio_root_user"),
            args.config.require_secret("minio_root_password"),
        )

        minio_env_secret = Secret(
            "minio-env-secret",
            metadata=ObjectMetaArgs(
                name="argo-artifacts-env-configuration",
                namespace=self.minio_tenant_ns.metadata.name,
            ),
            type="Opaque",
            string_data={
                "config.env": minio_config_env,
            },
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[self.minio_tenant_ns]),
            ),
        )

        self.minio_tenant = Chart(
            "minio-tenant",
            namespace=self.minio_tenant_ns.metadata.name,
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
                        {"name": "ingress"},
                        {"name": "egress"},
                    ],
                    "certificate": {
                        "requestAutoCert": "true",
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
                            "console": self.minio_fqdn,
                            "minio": [
                                Output.concat(self.minio_fqdn, "/api"),
                                self.minio_cluster_url,
                            ],
                        }
                    },
                    "pools": [
                        {
                            "servers": 1,
                            "name": "argo-artifacts-pool-0",
                            "size": args.config.require("minio_pool_size"),
                            "volumesPerServer": 1,
                            "storageClassName": args.storage_classes.encrypted_storage_class.metadata.name,
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
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(
                    depends_on=[
                        minio_env_secret,
                        self.minio_operator,
                        self.minio_tenant_ns,
                    ]
                ),
            ),
        )

        self.minio_ingress = Ingress(
            "minio-ingress",
            metadata=ObjectMetaArgs(
                name="minio-ingress",
                namespace=self.minio_tenant_ns.metadata.name,
                annotations={
                    "nginx.ingress.kubernetes.io/proxy-body-size": "0",
                    "nginx.ingress.kubernetes.io/force-ssl-redirect": "true",
                    "cert-manager.io/cluster-issuer": tls_issuer_names[
                        args.tls_environment
                    ],
                },
            ),
            spec=IngressSpecArgs(
                ingress_class_name="nginx",
                rules=[
                    IngressRuleArgs(
                        host=self.minio_fqdn,
                        http={
                            "paths": [
                                {
                                    "path": "/",
                                    "path_type": "Prefix",
                                    "backend": IngressBackendArgs(
                                        service=IngressServiceBackendArgs(
                                            name="argo-artifacts-console",
                                            port={"number": 9090},
                                        )
                                    ),
                                }
                            ]
                        },
                    )
                ],
                tls=[
                    IngressTLSArgs(
                        hosts=[self.minio_fqdn],
                        secret_name="argo-artifacts-ingress-tls",
                    )
                ],
            ),
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[self.minio_tenant]),
            ),
        )

        self.minio_tenant_name = self.minio_tenant.name
        self.register_outputs(
            {
                "minio_ingress": self.minio_ingress,
                "minio_tenant": self.minio_tenant,
                "minio_operator": self.minio_operator,
                "minio_env_secret": minio_env_secret,
                "minio_tenant_ns": self.minio_tenant_ns,
                "minio_operator_ns": self.minio_operator_ns,
            }
        )
