from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.core.v1 import Namespace
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs
from pulumi_kubernetes.helm.v3 import Release
from pulumi_kubernetes.helm.v4 import RepositoryOptsArgs
from pulumi_kubernetes.storage.v1 import StorageClass

from enums import K8sEnvironment, PodSecurityStandard

STORAGE_CLASS_NAME = "fridge"


class StorageClassesArgs:
    def __init__(
        self,
        k8s_environment: K8sEnvironment,
        azure_disk_encryption_set: str | None = None,
        azure_resource_group: str | None = None,
        azure_subscription_id: str | None = None,
    ) -> None:
        self.k8s_environment = k8s_environment
        self.azure_disk_encryption_set = azure_disk_encryption_set
        self.azure_resource_group = azure_resource_group
        self.azure_subscription_id = azure_subscription_id


class StorageClasses(ComponentResource):
    def __init__(
        self, name: str, args: StorageClassesArgs, opts: ResourceOptions | None = None
    ) -> None:
        super().__init__("fridge:StorageClasses", name, None, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        k8s_environment = args.k8s_environment

        if k8s_environment == K8sEnvironment.AKS:
            storage_class = StorageClass(
                "fridge_storage_class",
                allow_volume_expansion=True,
                metadata=ObjectMetaArgs(
                    name=STORAGE_CLASS_NAME,
                ),
                parameters={
                    "diskEncryptionSetID": f"/subscriptions/{args.azure_subscription_id}/resourceGroups/{args.azure_resource_group}/providers/Microsoft.Compute/diskEncryptionSets/{args.azure_disk_encryption_set}",
                    "kind": "managed",
                    "skuname": "StandardSSD_LRS",
                },
                provisioner="disk.csi.azure.com",
                opts=child_opts,
            )

            rwm_class_name = "azurefile"
        elif k8s_environment == K8sEnvironment.AKS:
            longhorn_ns = Namespace(
                "longhorn-system",
                metadata=ObjectMetaArgs(
                    name="longhorn-system",
                    labels={} | PodSecurityStandard.PRIVILEGED.value,
                ),
                opts=child_opts,
            )

            longhorn = Release(
                "longhorn",
                namespace=longhorn_ns.metadata.name,
                chart="longhorn",
                version="1.9.0",
                repository_opts=RepositoryOptsArgs(
                    repo="https://charts.longhorn.io",
                ),
                # Add a toleration for the GPU node, to allow Longhorn to schedule pods/create volumes there
                values={
                    "global": {
                        "tolerations": [
                            {
                                "key": "gpu.intel.com/i915",
                                "operator": "Exists",
                                "effect": "NoSchedule",
                            }
                        ]
                    },
                    "defaultSettings": {
                        "taintToleration": "gpu.intel.com/i915:NoSchedule"
                    },
                    "persistence": {"defaultClassReplicaCount": 2},
                },
                opts=ResourceOptions.merge(
                    child_opts,
                    ResourceOptions(depends_on=[longhorn_ns]),
                ),
            )

            storage_class = StorageClass(
                "fridge_storage_class",
                allow_volume_expansion=True,
                metadata=ObjectMetaArgs(
                    name=STORAGE_CLASS_NAME,
                ),
                parameters={
                    "dataLocality": "best-effort",
                    "fsType": "ext4",
                    "numberOfReplicas": "2",
                    "staleReplicaTimeout": "2880",
                },
                provisioner="driver.longhorn.io",
                opts=ResourceOptions.merge(
                    child_opts,
                    ResourceOptions(depends_on=[longhorn]),
                ),
            )

        rwm_class_name = storage_class.metadata.name

        self.fridge_storage_class = storage_class
        self.fridge_rwm_class_name = rwm_class_name
