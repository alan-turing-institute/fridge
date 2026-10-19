import hashlib
import json

import pulumi
from pulumi import ComponentResource, Output, ResourceOptions
from string import Template
from enums import K8sEnvironment, PodSecurityStandard
from pulumi_kubernetes.core.v1 import ConfigMap, Namespace
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs
from pulumi_kubernetes.yaml import ConfigGroup

# Upstream registries mirrored by Harbor, and the Harbor proxy-cache project for each
HARBOR_MIRRORS = {
    "docker.io": "proxy-docker.io",
    "quay.io": "proxy-quay.io",
    "ghcr.io": "proxy-ghcr.io",
    "registry.k8s.io": "proxy-k8s.io",
}

# Where the DaemonSet installs the Harbor CA bundle on each k3s node
K3S_HARBOR_CA_PATH = "/etc/rancher/k3s/harbor-ca.pem"


def k3s_registry_files(harbor_fqdn: str, ca_bundle: str | None) -> dict[str, str]:
    """
    Build the k3s registry configuration for pulling through Harbor.

    Returns registries.yaml (read by k3s on startup), the equivalent containerd
    hosts.toml for each registry (read by containerd on every pull, so changes
    apply without restarting k3s) and, if Harbor's certificate is not signed by
    a publicly trusted CA, the CA bundle needed to verify it.
    """
    files: dict[str, str] = {}

    registries_yaml = ["mirrors:"]
    for registry, project in HARBOR_MIRRORS.items():
        registries_yaml += [
            f"  {registry}:",
            "    endpoint:",
            f"      - https://{harbor_fqdn}/v2/{project}",
        ]
    if ca_bundle:
        registries_yaml += [
            "configs:",
            f'  "{harbor_fqdn}":',
            "    tls:",
            f"      ca_file: {K3S_HARBOR_CA_PATH}",
        ]
    files["registries.yaml"] = "\n".join(registries_yaml) + "\n"

    ca_line = f'  ca = "{K3S_HARBOR_CA_PATH}"\n' if ca_bundle else ""
    for registry, project in HARBOR_MIRRORS.items():
        files[f"{registry}.hosts.toml"] = (
            f'[host."https://{harbor_fqdn}/v2/{project}"]\n'
            '  capabilities = ["pull", "resolve"]\n'
            "  override_path = true\n" + ca_line
        )
    if ca_bundle:
        # Images referenced directly by the Harbor FQDN
        files[f"{harbor_fqdn}.hosts.toml"] = (
            f'server = "https://{harbor_fqdn}"\n\n'
            f'[host."https://{harbor_fqdn}"]\n'
            '  capabilities = ["pull", "resolve", "push"]\n' + ca_line
        )
        files["harbor-ca.pem"] = ca_bundle

    return files


class ContainerRuntimeConfigArgs:
    def __init__(
        self,
        config: pulumi.config.Config,
        harbor_fqdn: Output[str],
        harbor_ca_bundle: Output[str | None],
        k8s_environment: K8sEnvironment,
    ) -> None:
        self.config = config
        self.harbor_ca_bundle = harbor_ca_bundle
        self.harbor_fqdn = harbor_fqdn
        self.k8s_environment = k8s_environment


class ContainerRuntimeConfig(ComponentResource):
    def __init__(
        self,
        name: str,
        args: ContainerRuntimeConfigArgs,
        opts: ResourceOptions | None = None,
    ):
        super().__init__("fridge:ContainerRuntimeConfig", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        self.config_ns = Namespace(
            "container-runtime-config-ns",
            metadata=ObjectMetaArgs(
                name="containerd-config",
                labels={} | PodSecurityStandard.PRIVILEGED.value,
            ),
            opts=child_opts,
        )

        match args.k8s_environment:
            case K8sEnvironment.AKS:
                with open("k8s/containerd/registry_mirrors.yaml", "r") as file:
                    yaml_template = file.read()

                registry_mirror_config = Output.all(
                    namespace=self.config_ns.metadata.name,
                    harbor_fqdn=args.harbor_fqdn,
                ).apply(
                    lambda values: Template(yaml_template).substitute(
                        namespace=values["namespace"],
                        harbor_fqdn=values["harbor_fqdn"],
                    )
                )

            case K8sEnvironment.DAWN:
                with open("k8s/containerd/dawn_registries.yaml", "r") as file:
                    yaml_template = file.read()

                k3s_data_dir = args.config.get("k3s_data_dir") or "/var/lib/rancher/k3s"
                registry_files = Output.all(
                    args.harbor_fqdn, args.harbor_ca_bundle
                ).apply(lambda values: k3s_registry_files(*values))

                self.registry_config = ConfigMap(
                    "k3s-registry-config",
                    metadata=ObjectMetaArgs(
                        namespace=self.config_ns.metadata.name,
                        name="k3s-registry-config",
                    ),
                    data=registry_files,
                    opts=ResourceOptions.merge(
                        child_opts,
                        ResourceOptions(depends_on=[self.config_ns]),
                    ),
                )

                registry_mirror_config = Output.all(
                    namespace=self.config_ns.metadata.name,
                    config_map=self.registry_config.metadata.name,
                    files=registry_files,
                ).apply(
                    lambda values: Template(yaml_template).substitute(
                        namespace=values["namespace"],
                        config_map=values["config_map"],
                        config_hash=hashlib.sha256(
                            json.dumps(values["files"], sort_keys=True).encode()
                        ).hexdigest()[:16],
                        k3s_containerd_dir=f"{k3s_data_dir}/agent/etc/containerd",
                    )
                )

        self.configure_runtime = registry_mirror_config.apply(
            lambda yaml_content: ConfigGroup(
                "configure-container-runtime",
                yaml=[yaml_content],
                opts=ResourceOptions.merge(
                    child_opts,
                    ResourceOptions(
                        depends_on=[self.config_ns],
                    ),
                ),
            )
        )
