from string import Template

from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.yaml import ConfigFile, ConfigGroup

from enums import K8sEnvironment


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
        super().__init__("fridge:NetworkPolicies", name, None, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        match args.k8s_environment:
            case K8sEnvironment.AKS:
                storage_class_yaml = Template(
                    open("k8s/storage_classes/aks/ssd_standard_lrs_byok.yaml").read()
                ).substitute(
                    disk_encryption_set=args.azure_disk_encryption_set,
                    resource_group=args.azure_resource_group,
                    subscription_id=args.azure_subscription_id,
                )
                storage_class = ConfigGroup(
                    "fridge_storage_class",
                    yaml=[storage_class_yaml],
                    opts=child_opts,
                )
            case K8sEnvironment.DAWN:
                storage_class = ConfigFile(
                    "fridge_storage_class",
                    file="k8s/storage_classes/dawn/cinder.yaml",
                )

        self.fridge_storage_class = storage_class
