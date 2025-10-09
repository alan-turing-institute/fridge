import pulumi
from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.apps.v1 import Deployment, DeploymentSpecArgs
from pulumi_kubernetes.core.v1 import (
    ContainerArgs,
    ContainerPortArgs,
    EnvVarArgs,
    Namespace,
    PodSpecArgs,
    PodTemplateSpecArgs,
    Service,
    ServiceSpecArgs,
    VolumeArgs,
    VolumeMountArgs,
)
from pulumi_kubernetes.meta.v1 import LabelSelectorArgs, ObjectMetaArgs


from enums import K8sEnvironment, PodSecurityStandard


class PrivateAPIProxyArgs:
    def __init__(
        self,
        config: pulumi.config.Config,
        k8s_environment: K8sEnvironment,
    ):
        self.config = config
        self.k8s_environment = k8s_environment


class PrivateAPIProxy(ComponentResource):
    def __init__(
        self, name: str, args: PrivateAPIProxyArgs, opts: ResourceOptions | None = None
    ):
        super().__init__("fridge:k8s:PrivateAPIProxy", name, None, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        self.api_proxy_ns = Namespace(
            "api-proxy-ns",
            metadata=ObjectMetaArgs(
                name="api-proxy",
                labels={} | PodSecurityStandard.PRIVILEGED.value,
            ),
            opts=child_opts,
        )

        self.api_proxy = Deployment(
            "api-proxy",
            metadata=ObjectMetaArgs(
                namespace=self.api_proxy_ns.metadata.name,
            ),
            spec=DeploymentSpecArgs(
                selector=LabelSelectorArgs(
                    match_labels={"app": "api-proxy"},
                ),
                replicas=1,
                template=PodTemplateSpecArgs(
                    metadata=ObjectMetaArgs(
                        labels={"app": "api-proxy"},
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
                                    EnvVarArgs(name="PASSWORD_ACCESS", value="true"),
                                    EnvVarArgs(name="SUDO_ACCESS", value="false"),
                                    EnvVarArgs(
                                        name="USER_NAME", value="fridgeoperator"
                                    ),
                                    EnvVarArgs(
                                        name="USER_PASSWORD",
                                        value=args.config.require("api_ssh_password"),
                                    ),
                                    EnvVarArgs(
                                        name="DOCKER_MODS",
                                        value="linuxserver/mods:openssh-server-ssh-tunnel",
                                    ),
                                ],
                                volume_mounts=[
                                    VolumeMountArgs(
                                        name="ssh-config",
                                        mount_path="/config",
                                    )
                                ],
                            ),
                        ],
                        volumes=[
                            VolumeArgs(
                                name="ssh-config",
                                empty_dir={},
                            ),
                        ],
                    ),
                ),
            ),
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[self.api_proxy_ns]),
            ),
        )

        self.api_proxy_service = Service(
            "api-proxy-service",
            metadata=ObjectMetaArgs(
                name="api-proxy-service",
                namespace=self.api_proxy_ns.metadata.name,
            ),
            spec=ServiceSpecArgs(
                selector=self.api_proxy.spec.template.metadata.labels,
                ports=[{"protocol": "TCP", "port": 2500, "targetPort": 2222}],
                type="ClusterIP",
            ),
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[self.api_proxy]),
            ),
        )
