import pulumi
from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.apps.v1 import (
    Deployment,
    DeploymentSpecArgs,
    DeploymentStrategyArgs,
)
from pulumi_kubernetes.core.v1 import (
    CapabilitiesArgs,
    ConfigMap,
    ConfigMapVolumeSourceArgs,
    ContainerArgs,
    ContainerPortArgs,
    EnvVarArgs,
    Namespace,
    PersistentVolumeClaim,
    PersistentVolumeClaimSpecArgs,
    PersistentVolumeClaimVolumeSourceArgs,
    PodSpecArgs,
    PodTemplateSpecArgs,
    SecurityContextArgs,
    Service,
    ServicePortArgs,
    ServiceSpecArgs,
    VolumeArgs,
    VolumeMountArgs,
    VolumeResourceRequirementsArgs,
)
from pulumi_kubernetes.meta.v1 import LabelSelectorArgs, ObjectMetaArgs

from enums import PodSecurityStandard, SoftwareVersion


class VpnServerArgs:
    def __init__(self, config: pulumi.config.Config) -> None:
        self.config = config


class VpnServer(ComponentResource):
    def __init__(
        self, name: str, args: VpnServerArgs, opts: ResourceOptions | None = None
    ) -> None:
        super().__init__("fridge:fridge-access-cluster:VpnServer", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        self.vpn_ns = Namespace(
            "vpn-ns",
            metadata=ObjectMetaArgs(
                name="vpn-server",
                labels={} | PodSecurityStandard.PRIVILEGED.value,
            ),
            opts=child_opts,
        )

        self.haproxy_config = ConfigMap(
            "haproxy-config",
            metadata=ObjectMetaArgs(
                namespace=self.vpn_ns.metadata.name,
                name="vpn-proxy-config",
            ),
            data={
                "haproxy.cfg": """

global
  log stdout format raw local0

defaults
  mode tcp
  timeout connect 30s
  timeout client 3600s
  timeout server 3600s

frontend fridge_api_in
    bind *:8000
    default_backend fridge_api_out

backend fridge_api_out
    server fridge_api 10.20.1.60:443 check

frontend home_tre_in
    bind *:8001
    default_backend home_tre_out

backend home_tre_out
    server home_tre test-netbird-deploy.netbird.cloud:8000 check
""",
            },
        )

        netbird_config = args.config.require_object("netbird")

        self.netbird_data_volume = PersistentVolumeClaim(
            "netbird-data",
            metadata=ObjectMetaArgs(
                namespace=self.vpn_ns.metadata.name,
                name="netbird-data",
            ),
            spec=PersistentVolumeClaimSpecArgs(
                access_modes=["ReadWriteOnce"],
                resources=VolumeResourceRequirementsArgs(requests={"storage": "100Mi"}),
            ),
            opts=child_opts,
        )

        self.vpn_deployment = Deployment(
            "netbird-proxy",
            metadata=ObjectMetaArgs(
                namespace=self.vpn_ns.metadata.name,
            ),
            spec=DeploymentSpecArgs(
                selector=LabelSelectorArgs(match_labels={"app": "netbird-proxy"}),
                strategy=DeploymentStrategyArgs(type="Recreate"),
                replicas=1,
                template=PodTemplateSpecArgs(
                    metadata=ObjectMetaArgs(
                        labels={"app": "netbird-proxy"},
                    ),
                    spec=PodSpecArgs(
                        containers=[
                            ContainerArgs(
                                name="netbird-proxy",
                                image=f"netbirdio/netbird:{SoftwareVersion.NETBIRD.value}",
                                env=[
                                    EnvVarArgs(
                                        name="NB_SETUP_KEY",
                                        value=netbird_config["setup_key"],
                                    ),
                                    EnvVarArgs(
                                        name="NB_MANAGEMENT_URL",
                                        value=netbird_config["management_url"],
                                    ),
                                    EnvVarArgs(
                                        name="NB_HOSTNAME",
                                        value="fridge-access",
                                    ),
                                ],
                                volume_mounts=[
                                    VolumeMountArgs(
                                        name="netbird-data",
                                        mount_path="/var/lib/netbird",
                                    ),
                                ],
                                security_context=SecurityContextArgs(
                                    capabilities=CapabilitiesArgs(
                                        add=[
                                            "NET_ADMIN",
                                            "SYS_RESOURCE",
                                            "SYS_ADMIN",
                                        ]
                                    ),
                                ),
                            ),
                            ContainerArgs(
                                name="haproxy",
                                image=f"haproxy:{SoftwareVersion.HAPROXY.value}",
                                ports=[
                                    ContainerPortArgs(
                                        container_port=8000, protocol="TCP"
                                    )
                                ],
                                volume_mounts=[
                                    VolumeMountArgs(
                                        name="haproxy-config",
                                        mount_path="/usr/local/etc/haproxy/haproxy.cfg",
                                        sub_path="haproxy.cfg",
                                    ),
                                ],
                            ),
                        ],
                        volumes=[
                            VolumeArgs(
                                name="netbird-data",
                                persistent_volume_claim=PersistentVolumeClaimVolumeSourceArgs(
                                    claim_name=self.netbird_data_volume.metadata.name
                                ),
                            ),
                            VolumeArgs(
                                name="haproxy-config",
                                config_map=ConfigMapVolumeSourceArgs(
                                    name=self.haproxy_config.metadata.name
                                ),
                            ),
                        ],
                    ),
                ),
            ),
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(
                    depends_on=[
                        self.haproxy_config,
                        self.netbird_data_volume,
                        self.vpn_ns,
                    ]
                ),
            ),
        )

        # this service exposes the netbird proxy internally, but only to the access cluster
        # ideally, want to point the internal load balancer at this, so the isolated cluster can talk to it

        self.netbird_svc = Service(
            "netbird-proxy-svc",
            metadata=ObjectMetaArgs(
                namespace=self.vpn_ns.metadata.name,
                name="netbird-proxy-svc",
            ),
            spec=ServiceSpecArgs(
                selector=LabelSelectorArgs(match_labels={"app": "netbird-proxy"}),
                ports=[
                    ServicePortArgs(
                        name="vpn-port",
                        port=8000,
                        target_port=8000,
                        protocol="TCP",
                    )
                ],
                type="ClusterIP",
            ),
            opts=ResourceOptions.merge(
                child_opts, ResourceOptions(depends_on=[self.vpn_deployment])
            ),
        )
