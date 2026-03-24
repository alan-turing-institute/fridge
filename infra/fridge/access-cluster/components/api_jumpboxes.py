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


class APIJumpboxesArgs:
    def __init__(
        self,
        config: pulumi.config.Config,
        k8s_environment: K8sEnvironment,
    ):
        self.config = config
        self.k8s_environment = k8s_environment


class APIJumpboxes(ComponentResource):
    def __init__(
        self, name: str, args: APIJumpboxesArgs, opts: ResourceOptions | None = None
    ):
        super().__init__("fridge:k8s:APIJumpboxes", name, None, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        # Deploy namespaces
        self.fridge_api_jumpbox_ns = Namespace(
            "fridge-api-jumpbox-ns",
            metadata=ObjectMetaArgs(
                name="fridge-api-jumpbox",
                labels={} | PodSecurityStandard.PRIVILEGED.value,
            ),
            opts=child_opts,
        )

        self.k8s_api_jumpbox_ns = Namespace(
            "k8s-api-jumpbox-ns",
            metadata=ObjectMetaArgs(
                name="k8s-api-jumpbox",
                labels={} | PodSecurityStandard.PRIVILEGED.value,
            ),
            opts=child_opts,
        )

        self.fridge_ssh_key_secret = Secret(
            "fridge-api-jumpbox-ssh-key-secret",
            metadata=ObjectMetaArgs(
                namespace=self.fridge_api_jumpbox_ns.metadata.name,
            ),
            string_data={
                "authorized_keys": args.config.require("user_ssh_public_key"),
            },
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[self.fridge_api_jumpbox_ns]),
            ),
        )

        self.k8s_api_ssh_key_secret = Secret(
            "k8s-api-jumpbox-ssh-key-secret",
            metadata=ObjectMetaArgs(
                namespace=self.k8s_api_jumpbox_ns.metadata.name,
            ),
            string_data={
                "authorized_keys": args.config.require("admin_ssh_public_key"),
            },
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[self.k8s_api_jumpbox_ns]),
            ),
        )

        # Deploy config script

        # ConfigMaps are namespaced, so need separate ones for each jumpbox
        script_path = Path(__file__).parent / "scripts" / "ssh_config.sh"

        self.fridge_api_jumpbox_config_script = ConfigMap(
            "fridge-api-jumpbox-config-script",
            metadata=ObjectMetaArgs(
                namespace=self.fridge_api_jumpbox_ns.metadata.name,
            ),
            data={
                "setup_ssh_server.sh": script_path.read_text(),
            },
            opts=child_opts,
        )

        self.k8s_api_jumpbox_config_script = ConfigMap(
            "k8s-api-jumpbox-config-script",
            metadata=ObjectMetaArgs(
                namespace=self.k8s_api_jumpbox_ns.metadata.name,
            ),
            data={
                "setup_ssh_server.sh": script_path.read_text(),
            },
            opts=child_opts,
        )

        # Deploy jumpbox pods
        self.fridge_api_jumpbox = Deployment(
            "fridge-api-jumpbox",
            metadata=ObjectMetaArgs(
                namespace=self.fridge_api_jumpbox_ns.metadata.name,
            ),
            spec=DeploymentSpecArgs(
                selector=LabelSelectorArgs(
                    match_labels={"app": "fridge-api-jumpbox"},
                ),
                replicas=1,
                template=PodTemplateSpecArgs(
                    metadata=ObjectMetaArgs(
                        labels={"app": "fridge-api-jumpbox"},
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
                                    secret_name=self.fridge_ssh_key_secret.metadata.name,
                                ),
                            ),
                            VolumeArgs(
                                name="setup-script",
                                config_map=ConfigMapVolumeSourceArgs(
                                    name=self.fridge_api_jumpbox_config_script.metadata.name,
                                    default_mode=0o755,
                                ),
                            ),
                        ],
                    ),
                ),
            ),
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[self.fridge_api_jumpbox_ns]),
            ),
        )

        self.k8s_api_jumpbox = Deployment(
            "k8s-api-jumpbox",
            metadata=ObjectMetaArgs(
                namespace=self.k8s_api_jumpbox_ns.metadata.name,
            ),
            spec=DeploymentSpecArgs(
                selector=LabelSelectorArgs(
                    match_labels={"app": "k8s-api-jumpbox"},
                ),
                replicas=1,
                template=PodTemplateSpecArgs(
                    metadata=ObjectMetaArgs(
                        labels={"app": "k8s-api-jumpbox"},
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
                                    secret_name=self.k8s_api_ssh_key_secret.metadata.name,
                                ),
                            ),
                            VolumeArgs(
                                name="setup-script",
                                config_map=ConfigMapVolumeSourceArgs(
                                    name=self.k8s_api_jumpbox_config_script.metadata.name,
                                    default_mode=0o755,
                                ),
                            ),
                        ],
                    ),
                ),
            ),
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[self.k8s_api_jumpbox_ns]),
            ),
        )

        # Expose jumpboxes via ClusterIP services for use by Ingress Nginx

        self.fridge_api_jumpbox_service = Service(
            "fridge-api-jumpbox-service",
            metadata=ObjectMetaArgs(
                name="fridge-api-jumpbox-service",
                namespace=self.fridge_api_jumpbox.metadata.name,
            ),
            spec=ServiceSpecArgs(
                selector=self.fridge_api_jumpbox.spec.template.metadata.labels,
                ports=[{"protocol": "TCP", "port": 2222, "targetPort": 2222}],
                type="ClusterIP",
            ),
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[self.fridge_api_jumpbox]),
            ),
        )

        self.k8s_api_jumpbox_service = Service(
            "k8s-api-jumpbox-service",
            metadata=ObjectMetaArgs(
                name="k8s-api-jumpbox-service",
                namespace=self.k8s_api_jumpbox.metadata.name,
            ),
            spec=ServiceSpecArgs(
                selector=self.k8s_api_jumpbox.spec.template.metadata.labels,
                ports=[{"protocol": "TCP", "port": 2222, "targetPort": 2222}],
                type="ClusterIP",
            ),
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[self.k8s_api_jumpbox]),
            ),
        )
