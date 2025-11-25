import pulumi
from pathlib import Path
from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.apps.v1 import Deployment, DeploymentSpecArgs
from pulumi_kubernetes.core.v1 import (
    ConfigMap,
    ConfigMapVolumeSourceArgs,
    ContainerArgs,
    ContainerPortArgs,
    EnvVarArgs,
    Namespace,
    PodSpecArgs,
    PodTemplateSpecArgs,
    Secret,
    SecretVolumeSourceArgs,
    Service,
    ServiceSpecArgs,
    VolumeArgs,
    VolumeMountArgs,
)
from pulumi_kubernetes.meta.v1 import LabelSelectorArgs, ObjectMetaArgs


from enums import K8sEnvironment, PodSecurityStandard


class FridgeAPIJumpboxArgs:
    def __init__(
        self,
        config: pulumi.config.Config,
        k8s_environment: K8sEnvironment,
    ):
        self.config = config
        self.k8s_environment = k8s_environment


class FridgeAPIJumpbox(ComponentResource):
    def __init__(
        self, name: str, args: FridgeAPIJumpboxArgs, opts: ResourceOptions | None = None
    ):
        super().__init__("fridge:k8s:FridgeAPIJumpbox", name, None, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        self.api_jumpbox_ns = Namespace(
            "api-jumpbox-ns",
            metadata=ObjectMetaArgs(
                name="api-jumpbox",
                labels={} | PodSecurityStandard.PRIVILEGED.value,
            ),
            opts=child_opts,
        )

        self.ssh_key_secret = Secret(
            "api-jumpbox-ssh-key-secret",
            metadata=ObjectMetaArgs(
                namespace=self.api_jumpbox_ns.metadata.name,
            ),
            string_data={
                "authorized_keys": args.config.require("jumpbox_ssh_public_key"),
            },
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[self.api_jumpbox_ns]),
            ),
        )

        script_path = Path(__file__).parent / "scripts" / "ssh_config.sh"

        self.api_jumpbox_config_script = ConfigMap(
            "api-jumpbox-config-script",
            metadata=ObjectMetaArgs(
                namespace=self.api_jumpbox_ns.metadata.name,
            ),
            data={
                "setup_ssh_server.sh": script_path.read_text(),
            },
            opts=child_opts,
        )

        self.api_jumpbox = Deployment(
            "api-jumpbox",
            metadata=ObjectMetaArgs(
                namespace=self.api_jumpbox_ns.metadata.name,
            ),
            spec=DeploymentSpecArgs(
                selector=LabelSelectorArgs(
                    match_labels={"app": "api-jumpbox"},
                ),
                replicas=1,
                template=PodTemplateSpecArgs(
                    metadata=ObjectMetaArgs(
                        labels={"app": "api-jumpbox"},
                    ),
                    spec=PodSpecArgs(
                        containers=[
                            ContainerArgs(
                                name="ssh-server",
                                image="linuxserver/openssh-server:latest",
                                ports=[ContainerPortArgs(container_port=2222)],
                                env=[
                                    EnvVarArgs(name="PUID", value="1000"),
                                    EnvVarArgs(name="PGID", value="1000"),
                                    EnvVarArgs(name="PASSWORD_ACCESS", value="false"),
                                    EnvVarArgs(
                                        name="PUBLIC_KEY_FILE",
                                        value="/pubkey/authorized_keys",
                                    ),
                                    EnvVarArgs(name="SUDO_ACCESS", value="false"),
                                    EnvVarArgs(
                                        name="USER_NAME", value="fridgeoperator"
                                    ),
                                    EnvVarArgs(name="LOG_STDOUT", value="true"),
                                    EnvVarArgs(name="SHELL_NOLOGIN", value="true"),
                                ],
                                volume_mounts=[
                                    VolumeMountArgs(
                                        name="ssh-config",
                                        mount_path="/config",
                                    ),
                                    VolumeMountArgs(
                                        name="ssh-public-key",
                                        mount_path="/pubkey",
                                        read_only=True,
                                    ),
                                    VolumeMountArgs(
                                        name="setup-script",
                                        mount_path="/custom-cont-init.d/",
                                        read_only=True,
                                    ),
                                ],
                            ),
                        ],
                        volumes=[
                            VolumeArgs(
                                name="ssh-config",
                                empty_dir={},
                            ),
                            VolumeArgs(
                                name="ssh-public-key",
                                secret=SecretVolumeSourceArgs(
                                    secret_name=self.ssh_key_secret.metadata.name,
                                ),
                            ),
                            VolumeArgs(
                                name="setup-script",
                                config_map=ConfigMapVolumeSourceArgs(
                                    name=self.api_jumpbox_config_script.metadata.name,
                                    default_mode=0o755,
                                ),
                            ),
                        ],
                    ),
                ),
            ),
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[self.api_jumpbox_ns]),
            ),
        )

        self.api_jumpbox_service = Service(
            "api-jumpbox-service",
            metadata=ObjectMetaArgs(
                name="api-jumpbox-service",
                namespace=self.api_jumpbox_ns.metadata.name,
            ),
            spec=ServiceSpecArgs(
                selector=self.api_jumpbox.spec.template.metadata.labels,
                ports=[{"protocol": "TCP", "port": 2500, "targetPort": 2222}],
                type="ClusterIP",
            ),
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[self.api_jumpbox]),
            ),
        )
