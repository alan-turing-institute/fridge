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
from pulumi_kubernetes.discovery.v1 import EndpointSlice
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
    server fridge_api fridge-api-service:8000 check

frontend k8s_api_in
    bind *:6443
    default_backend k8s_api_out

backend k8s_api_out
    server k8s_api 10.20.1.4:443 check

frontend home_tre_in
    bind *:8001
    default_backend home_tre_out

backend home_tre_out
    server home_tre test-netbird-deploy.netbird.cloud:8000 check
""",
            },
        )

        netbird_config = args.config.require_object("netbird")

        # Use a PersistentVolumeClaim to store Netbird data, so that it persists across pod restarts
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

        # Create an internal service to expose the FRIDGE API to the VPN server
        # By using this, HAproxy can be pointed to the service instead of the specific IP address of the FRIDGE API
        # The FRIDGE API may have different IP addresses in different environments
        self.fridge_api_service = Service(
            "fridge-api-service",
            metadata=ObjectMetaArgs(
                name="fridge-api-service",
                namespace=self.vpn_ns.metadata.name,
            ),
            spec=ServiceSpecArgs(
                ports=[ServicePortArgs(port=8000, target_port=443, protocol="TCP")]
            ),
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(
                    depends_on=[
                        self.vpn_ns,
                    ]
                ),
            ),
        )

        # Create an EndpointSlice to point to the FRIDGE API IP address
        # Since this IP address is external to this K8s cluster, we need to create an EndpointSlice to point to it
        fridge_api_ip_raw = args.config.require("fridge_api_ip_address").strip()
        fridge_api_ip = fridge_api_ip_raw.split("/", 1)[0]
        self.fridge_api_endpoint = EndpointSlice(
            "fridge-api-endpoint",
            metadata=ObjectMetaArgs(
                name="fridge-api-endpoint",
                namespace=self.vpn_ns.metadata.name,
                labels={
                    "kubernetes.io/service-name": self.fridge_api_service.metadata.name
                },
            ),
            address_type="IPv4",
            endpoints=[{"addresses": [fridge_api_ip], "conditions": {"ready": True}}],
            ports=[{"name": "", "port": 443, "protocol": "TCP"}],
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(
                    depends_on=[
                        self.fridge_api_service,
                    ]
                ),
            ),
        )
