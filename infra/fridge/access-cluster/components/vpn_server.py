from string import Template

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

from enums import K8sEnvironment, PodSecurityStandard, SoftwareVersion


class VpnServerArgs:
    def __init__(self, config: pulumi.config.Config) -> None:
        self.config = config


class VpnServer(ComponentResource):
    def __init__(
        self, name: str, args: VpnServerArgs, opts: ResourceOptions | None = None
    ) -> None:
        super().__init__("fridge:fridge-access-cluster:VpnServer", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        k8s_environment = K8sEnvironment(args.config.require("k8s_env"))

        self.vpn_ns = Namespace(
            "vpn-ns",
            metadata=ObjectMetaArgs(
                name="vpn-server",
                labels={} | PodSecurityStandard.PRIVILEGED.value,
            ),
            opts=child_opts,
        )

        if k8s_environment == K8sEnvironment.AKS:
            isolated_k8s_api_endpoint = (
                f"{args.config.require('isolated_cluster_api_endpoint')}:443"
            )
        else:
            isolated_k8s_api_endpoint_raw = args.config.require(
                "isolated_cluster_api_endpoint"
            ).strip()
            isolated_k8s_api_endpoint = (
                f"{isolated_k8s_api_endpoint_raw.split('/', 1)[0]}:6443"
            )

        haproxy_cfg_file = Template(
            open("./k8s/haproxy/haproxy.cfg", "r").read()
        ).substitute(
            isolated_k8s_api_endpoint=isolated_k8s_api_endpoint,
        )

        self.haproxy_config = ConfigMap(
            "haproxy-config",
            metadata=ObjectMetaArgs(
                namespace=self.vpn_ns.metadata.name,
                name="vpn-proxy-config",
            ),
            data={"haproxy.cfg": haproxy_cfg_file},
            opts=child_opts,
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
                                        value=netbird_config["hostname"],
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
                                    ),
                                    ContainerPortArgs(
                                        container_port=6443, protocol="TCP"
                                    ),
                                    ContainerPortArgs(
                                        container_port=8001, protocol="TCP"
                                    ),
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
        if k8s_environment == K8sEnvironment.AKS:
            fridge_api_port = 443
        else:
            fridge_api_port = 30180

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
            ports=[{"name": "", "port": fridge_api_port, "protocol": "TCP"}],
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(
                    depends_on=[
                        self.fridge_api_service,
                    ]
                ),
            ),
        )
