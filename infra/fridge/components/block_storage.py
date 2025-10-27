import pulumi
from pulumi import ComponentResource, Output, ResourceOptions
from pulumi_kubernetes.core.v1 import PersistentVolumeClaim, PersistentVolumeClaimSpecArgs
from pulumi_kubernetes.core.v1 import ResourceRequirementsArgs
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs

from .storage_classes import StorageClasses

class BlockStorageArgs:
    def __init__(
        self,
        config: pulumi.config.Config,
        storage_classes: StorageClasses,
        storage_volume_claim_ns: str,
    ) -> None:
        self.config = config
        self.storage_classes = storage_classes
        self.storage_volume_claim_ns = storage_volume_claim_ns

class BlockStorage(ComponentResource):
    def __init__(
        self,
        name: str,
        args: BlockStorageArgs,
        opts: ResourceOptions | None = None,
    ) -> None:
        super().__init__("fridge:BlockStorage", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        # We assume the storage class supports dynamic provisioning
        block_storage_pvc = PersistentVolumeClaim(
            "block-storage",
            metadata=ObjectMetaArgs(
                name="block-storage-pvc", # TODO: Export this to argo pod templates?
                namespace=args.storage_volume_claim_ns,
            ),
            spec = PersistentVolumeClaimSpecArgs(
                storage_class_name=args.storage_classes.standard_storage_name,
                access_modes=["ReadWriteMany" if args.storage_classes.standard_supports_rwm else "ReadWriteOnce"],
                resources=ResourceRequirementsArgs(
                    requests={
                        "storage":"1Gi", # TODO: Get from config?
                    },
                )
            ),
        )
