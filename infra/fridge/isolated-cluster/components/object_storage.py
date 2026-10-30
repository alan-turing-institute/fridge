import hashlib
import re
import pulumi
from pulumi import ComponentResource, Output, ResourceOptions
from pulumi_kubernetes.apiextensions import CustomResource
from pulumi_kubernetes.core.v1 import Namespace, Secret
from pulumi_kubernetes.helm.v4 import Chart, RepositoryOptsArgs
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs
from pulumi_random import RandomPassword

from .storage_classes import StorageClasses
from enums import PodSecurityStandard, SoftwareVersion

_K8S_QUANTITY = re.compile(r"^\d+(\.\d+)?(Ki|Mi|Gi|Ti|Pi|Ei|k|M|G|T|P|E)$")


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

        seaweedfs_config = args.config.require_secret_object("seaweedfs")

        def validate_pool_size(config):
            size = config["pool_size"]
            if not isinstance(size, str) or not _K8S_QUANTITY.match(size):
                raise ValueError(
                    f"seaweedfs.pool_size '{size}' is not a valid Kubernetes quantity (e.g. 40Gi)"
                )
            return size

        seaweedfs_pool_size = seaweedfs_config.apply(validate_pool_size)
        seaweedfs_root_user = seaweedfs_config.apply(lambda config: config["root_user"])
        seaweed_root_password = seaweedfs_config.apply(
            lambda config: config["root_password"]
        )

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

        # Generate some credentials for Argo and Fridge to use for S3 access. These are stored in a secret and referenced by the SeaweedFS Helm chart.
        self.argo_s3_credentials = {
            "accessKey": RandomPassword(
                "argo-s3-access-key",
                length=32,
                special=False,
                opts=ResourceOptions.merge(
                    child_opts,
                    ResourceOptions(depends_on=[self.seaweedfs_ns]),
                ),
            ).result,
            "secretKey": RandomPassword(
                "argo-s3-secret-key",
                length=32,
                special=False,
                opts=ResourceOptions.merge(
                    child_opts,
                    ResourceOptions(depends_on=[self.seaweedfs_ns]),
                ),
            ).result,
        }

        # SeaweedFS's S3 gateway takes a single static identity, not a MinIO-style root user
        seaweedfs_s3_config = Output.json_dumps(
            {
                "identities": [
                    {
                        "name": "fridge",
                        "credentials": [
                            {
                                "accessKey": args.config.require_secret(
                                    "s3_access_key"
                                ),
                                "secretKey": args.config.require_secret(
                                    "s3_secret_key"
                                ),
                            }
                        ],
                        # Generic identity for the API: data only flows in through ingress and out through egress,
                        # so it can write (upload and delete) but not read ingress, and read but not write egress. No Admin.
                        # User-specific buckets and admin operations use credentials supplied by the caller.
                        "actions": [
                            "Write:ingress",
                            "List:ingress",
                            "Read:egress",
                            "List:egress",
                        ],
                    },
                    {
                        # Used by the data-copy workflow. Read is unscoped so that it can copy
                        # from any (including per-user) ingress bucket; write is limited to egress.
                        "name": "fridge-argo",
                        "credentials": [self.argo_s3_credentials],
                        "actions": ["Read", "List", "Write:egress"],
                    },
                    {
                        # Admin identity for bucket creation and other admin operations. Not given to the API:
                        # admins supply these credentials to it per request in the X-S3-* headers.
                        "name": "fridge-admin",
                        "credentials": [
                            {
                                "accessKey": args.config.require_secret(
                                    "s3_admin_access_key"
                                ),
                                "secretKey": args.config.require_secret(
                                    "s3_admin_secret_key"
                                ),
                            }
                        ],
                        "actions": ["Admin", "Read", "List", "Write"],
                    },
                ]
            },
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
                "adminUser": seaweedfs_root_user,
                "adminPassword": seaweed_root_password,
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
                    "port": 12535,  # default port, shown here for transparency
                    "grpcPort": 22535,  # default port, shown here for transparency
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
                            "size": seaweedfs_pool_size,
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
                    # Encrypt each chunk on the volume servers with its own key, kept in the filer metadata
                    "encryptVolumeData": True,
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
                    # The S3 gateway uploads chunks straight to the volume servers, so it needs its own
                    # encryption flag; filer.encryptVolumeData only covers writes that go through the filer
                    "extraArgs": ["-encryptVolumeData"],
                    # The S3 gateway only reads its identities at startup, so roll the pod whenever they change
                    "podAnnotations": {
                        "checksum/s3-config": seaweedfs_s3_config.apply(
                            lambda config: hashlib.sha256(config.encode()).hexdigest()
                        ),
                    },
                    "tlsSecret": "seaweedfs-tls",
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
