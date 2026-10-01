import pulumi
from pulumi import ComponentResource, Output, ResourceOptions
from pulumi_kubernetes.apiextensions import CustomResource
from pulumi_kubernetes.core.v1 import Namespace, Secret
from pulumi_kubernetes.helm.v4 import Chart, RepositoryOptsArgs
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs

from .storage_classes import StorageClasses
from enums import PodSecurityStandard, SoftwareVersion


class ObjectStorageArgs:
    def __init__(
        self,
        config: pulumi.config.Config,
        storage_classes: StorageClasses,
        cluster_issuer: CustomResource,
    ) -> None:
        self.config = config
        self.cluster_issuer = cluster_issuer
        self.storage_classes = storage_classes


class ObjectStorage(ComponentResource):
    def __init__(
        self, name: str, args: ObjectStorageArgs, opts: ResourceOptions | None = None
    ) -> None:
        super().__init__("fridge:k8s:ObjectStorage", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        self.seaweedfs_ns = Namespace(
            "seaweedfs-ns",
            metadata=ObjectMetaArgs(
                name="seaweedfs",
                labels={"seaweedfs-trust-bundle": "enabled"}
                | PodSecurityStandard.RESTRICTED.value,
            ),
            opts=child_opts,
        )

        self.seaweedfs_s3_url = Output.concat(
            "seaweedfs-s3.", self.seaweedfs_ns.metadata.name, ".svc.cluster.local"
        )

        # SeaweedFS's S3 gateway takes a single static identity, not a MinIO-style root user
        seaweedfs_s3_config = Output.format(
            """{{
                "identities": [
                    {{
                        "name": "fridge",
                        "credentials": [
                            {{"accessKey": "{0}", "secretKey": "{1}"}}
                        ],
                        "actions": ["Admin", "Read", "Write"]
                    }},
                    {{
                        "name": "anonymous",
                        "credentials": [],
                        "actions": [
                            "Read:ingress",
                            "Write:egress",
                        ]
                    }}
                ]
            }}""",
            args.config.require_secret("s3_access_key"),
            args.config.require_secret("s3_secret_key"),
        )

        seaweedfs_s3_secret = Secret(
            "seaweedfs-s3-secret",
            metadata=ObjectMetaArgs(
                name="seaweedfs-s3-config",
                namespace=self.seaweedfs_ns.metadata.name,
            ),
            type="Opaque",
            string_data={
                "seaweedfs_s3_config": seaweedfs_s3_config,
            },
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[self.seaweedfs_ns]),
            ),
        )

        self.seaweedfs_certificate = CustomResource(
            "seaweedfs-certificate",
            api_version="cert-manager.io/v1",
            kind="Certificate",
            metadata=ObjectMetaArgs(
                name="seaweedfs-tls",
                namespace=self.seaweedfs_ns.metadata.name,
            ),
            spec={
                "secretName": "seaweedfs-tls",
                "issuerRef": {
                    "name": args.cluster_issuer.metadata["name"],
                    "kind": "ClusterIssuer",
                },
                "dnsNames": [
                    self.seaweedfs_s3_url,
                ],
            },
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[self.seaweedfs_ns]),
            ),
        )

        seaweedfs_admin_secret = Secret(
            "seaweedfs-admin-secret",
            metadata=ObjectMetaArgs(
                name="seaweedfs-admin-secret",
                namespace=self.seaweedfs_ns.metadata.name,
            ),
            type="Opaque",
            string_data={
                "adminUser": "admin",
                "adminPassword": "admin",
            },
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[self.seaweedfs_ns]),
            ),
        )

        self.seaweedfs = Chart(
            "seaweedfs",
            namespace=self.seaweedfs_ns.metadata.name,
            chart="seaweedfs",
            version=SoftwareVersion.SEAWEEDFS.value,
            repository_opts=RepositoryOptsArgs(
                repo="https://seaweedfs.github.io/seaweedfs/helm",
            ),
            values={
                "admin": {
                    "enabled": True,
                    "port": 23646,
                    "grpcPort": 33646,
                    "secret": {
                        "existingSecret": seaweedfs_admin_secret.metadata.name,
                        "userKey": "adminUser",
                        "pwKey": "adminPassword",
                    },
                    "podSecurityContext": {
                        "enabled": True,
                        "fsGroup": 1000,
                        "runAsUser": 1000,
                        "runAsGroup": 1000,
                        "runAsNonRoot": True,
                        "seccompProfile": {
                            "type": "RuntimeDefault",
                        },
                    },
                    "containerSecurityContext": {
                        "enabled": True,
                        "allowPrivilegeEscalation": False,
                        "capabilities": {"drop": ["ALL"]},
                    },
                },
                "global": {
                    "seaweedfs": {
                        "enableSecurity": True,
                    },
                },
                "master": {
                    "replicas": 1,
                    "data": {
                        "type": "persistentVolumeClaim",
                        "size": "1Gi",
                        "storageClass": args.storage_classes.encrypted_storage_class.metadata.name,
                    },
                    "logs": {
                        "type": "emptyDir",
                    },
                    "podSecurityContext": {
                        "enabled": True,
                        "fsGroup": 1000,
                        "runAsUser": 1000,
                        "runAsGroup": 1000,
                        "runAsNonRoot": True,
                        "seccompProfile": {
                            "type": "RuntimeDefault",
                        },
                    },
                    "containerSecurityContext": {
                        "enabled": True,
                        "allowPrivilegeEscalation": False,
                        "capabilities": {"drop": ["ALL"]},
                    },
                },
                "volume": {
                    "replicas": 1,
                    "dataDirs": [
                        {
                            "name": "data",
                            "type": "persistentVolumeClaim",
                            "storageClass": args.storage_classes.encrypted_storage_class.metadata.name,
                            "size": "50Gi",
                            "maxVolumes": 0,
                        }
                    ],
                    "logs": {
                        "type": "emptyDir",
                    },
                    "podSecurityContext": {
                        "enabled": True,
                        "fsGroup": 1000,
                        "runAsUser": 1000,
                        "runAsGroup": 1000,
                        "runAsNonRoot": True,
                        "seccompProfile": {
                            "type": "RuntimeDefault",
                        },
                    },
                    "containerSecurityContext": {
                        "enabled": True,
                        "allowPrivilegeEscalation": False,
                        "capabilities": {"drop": ["ALL"]},
                    },
                },
                "filer": {
                    "replicas": 1,
                    "logs": {
                        "type": "emptyDir",
                    },
                    "data": {
                        "type": "persistentVolumeClaim",
                        "size": "5Gi",
                        "storageClass": args.storage_classes.encrypted_storage_class.metadata.name,
                    },
                    "podSecurityContext": {
                        "enabled": True,
                        "fsGroup": 1000,
                        "runAsUser": 1000,
                        "runAsGroup": 1000,
                        "runAsNonRoot": True,
                        "seccompProfile": {
                            "type": "RuntimeDefault",
                        },
                    },
                    "containerSecurityContext": {
                        "enabled": True,
                        "allowPrivilegeEscalation": False,
                        "capabilities": {"drop": ["ALL"]},
                    },
                },
                "s3": {
                    "enabled": True,
                    "replicas": 1,
                    "logs": {
                        "type": "emptyDir",
                    },
                    "httpsPort": 8334,
                    "enableAuth": True,
                    "existingConfigSecret": seaweedfs_s3_secret.metadata.name,
                    "tlsSecret": "seaweedfs-tls",
                    # createBuckets is disabled due to https://github.com/seaweedfs/seaweedfs/issues/10502; renable it once fixed upstream
                    # "createBuckets": [
                    #     {"name": "ingress", "anonymousRead": False},
                    #     {"name": "egress", "anonymousRead": True},
                    # ],
                    "podSecurityContext": {
                        "enabled": True,
                        "fsGroup": 1000,
                        "runAsUser": 1000,
                        "runAsGroup": 1000,
                        "runAsNonRoot": True,
                        "seccompProfile": {
                            "type": "RuntimeDefault",
                        },
                    },
                    "containerSecurityContext": {
                        "enabled": True,
                        "allowPrivilegeEscalation": False,
                        "capabilities": {"drop": ["ALL"]},
                    },
                },
            },
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(
                    depends_on=[
                        seaweedfs_s3_secret,
                        self.seaweedfs_certificate,
                        self.seaweedfs_ns,
                    ]
                ),
            ),
        )

        self.seaweedfs_s3_endpoint = Output.concat(
            "seaweedfs-s3.", self.seaweedfs_ns.metadata.name, ".svc.cluster.local:8334"
        )

        self.register_outputs(
            {
                "seaweedfs": self.seaweedfs,
                "seaweedfs_ns": self.seaweedfs_ns,
                "seaweedfs_s3_secret": seaweedfs_s3_secret,
                "seaweedfs_endpoint": self.seaweedfs_s3_endpoint,
            }
        )
