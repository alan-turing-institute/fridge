import pulumi
from pulumi import ComponentResource, Output, ResourceOptions
from pulumi_kubernetes import Provider
from pulumi_kubernetes.apps.v1 import Deployment, DeploymentSpecArgs
from pulumi_kubernetes.core.v1 import (
    ConfigMap,
    ContainerArgs,
    ContainerPortArgs,
    EnvVarArgs,
    Namespace,
    PodSpecArgs,
    PodTemplateSpecArgs,
    Service,
    VolumeArgs,
    VolumeMountArgs,
)
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs
from pulumi_kubernetes.meta.v1 import LabelSelectorArgs, ObjectMetaArgs


class DualClusterArgs:
    def __init__(
        self,
        access_kubeconfig: Provider,
        config: pulumi.config.Config,
        private_fqdn: pulumi.Output[str],
        private_kubeconfig: Provider,
    ):
        self.access_kubeconfig = access_kubeconfig
        self.config = config
        self.private_fqdn = private_fqdn
        self.private_kubeconfig = private_kubeconfig


class DualCluster(ComponentResource):
    def __init__(
        self, name: str, args: DualClusterArgs, opts: ResourceOptions | None = None
    ):
        super().__init__("custom:resource:DualCluster", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        # Deploy something to both clusters to verify connectivity

        api_proxy_ns = Namespace(
            "api-proxy-ns",
            metadata=ObjectMetaArgs(
                name="api-proxy", labels={}  # | PodSecurityStandard.RESTRICTED.value,
            ),
            opts=ResourceOptions.merge(
                child_opts, ResourceOptions(provider=args.access_kubeconfig)
            ),
        )

        self.ingress_nginx_ns = Namespace(
            "ingress-nginx-ns",
            metadata=ObjectMetaArgs(
                name="ingress-nginx",
                labels={},  # | PodSecurityStandard.RESTRICTED.value,
            ),
            opts=ResourceOptions.merge(
                child_opts, ResourceOptions(provider=args.access_kubeconfig)
            ),
        )

        self.ingress_nginx = Release(
            "ingress-nginx",
            ReleaseArgs(
                chart="ingress-nginx",
                version="4.13.2",
                repository_opts={"repo": "https://kubernetes.github.io/ingress-nginx"},
                namespace=self.ingress_nginx_ns.metadata.name,
                create_namespace=False,
                values={
                    "controller": {
                        "nodeSelector": {"kubernetes.io/os": "linux"},
                        "service": {
                            "externalTrafficPolicy": "Local",
                        },
                    },
                    "tcp": {
                        "2500": Output.concat(
                            api_proxy_ns.metadata.name, "/api-ssh-svc:2500"
                        ),
                    },
                },
            ),
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(
                    depends_on=self.ingress_nginx_ns, provider=args.access_kubeconfig
                ),
            ),
        )

        api_proxy_config = ConfigMap(
            "api-proxy-config",
            metadata=ObjectMetaArgs(
                namespace=api_proxy_ns.metadata.name,
                name="api-proxy-config",
            ),
            data={
                "nginx.conf": args.private_fqdn.apply(
                    lambda fqdn: f"""
worker_processes auto;

events {{
  worker_connections 1024;
}}

stream {{
  upstream private_api_server {{
    # Private API server FQDN:443
    server {fqdn}:443;
  }}

  server {{
    # TCP listener inside the pod
    listen 8443;

    # Timeouts suitable for long-lived kubectl streams
    proxy_connect_timeout 30s;
    proxy_timeout 3600s;

    # Pure TCP passthrough to the upstream
    proxy_pass private_api_server;

    proxy_ssl_server_name on;
    proxy_ssl_verify off;
    proxy_ssl_trusted_certificate /etc/nginx/conf.d/certs/api/certificate;
  }}
}}
""",
                )
            },
        )

        self.api_proxy = Deployment(
            "api-proxy",
            metadata=ObjectMetaArgs(
                namespace=api_proxy_ns.metadata.name,
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
                            ContainerArgs(
                                name="api-proxy",
                                image="nginx:latest",
                                ports=[ContainerPortArgs(container_port=8443)],
                                volume_mounts=[
                                    {
                                        "name": "api-proxy-config",
                                        "mountPath": "/etc/nginx/nginx.conf",
                                        "subPath": "nginx.conf",
                                        "readOnly": True,
                                    }
                                ],
                            ),
                        ],
                        volumes=[
                            {
                                "name": "api-proxy-config",
                                "configMap": {"name": api_proxy_config.metadata.name},
                            },
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
                ResourceOptions(
                    depends_on=self.ingress_nginx, provider=args.access_kubeconfig
                ),
            ),
        )

        self.api_ssh_svc = Service(
            "api-ssh-svc",
            metadata=ObjectMetaArgs(
                namespace=api_proxy_ns.metadata.name,
                name="api-ssh-svc",
            ),
            spec={
                "type": "ClusterIP",
                "ports": [{"port": 2500, "targetPort": 2222, "protocol": "TCP"}],
                "selector": {"app": "api-proxy"},
            },
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(
                    depends_on=self.api_proxy, provider=args.access_kubeconfig
                ),
            ),
        )

        self.api_proxy_svc = Service(
            "api-proxy-svc",
            metadata=ObjectMetaArgs(
                namespace=api_proxy_ns.metadata.name,
                name="api-proxy-svc",
            ),
            spec={
                "type": "ClusterIP",
                "ports": [{"port": 8443, "targetPort": 8443, "protocol": "TCP"}],
                "selector": {"app": "api-proxy"},
            },
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(
                    depends_on=self.api_proxy, provider=args.access_kubeconfig
                ),
            ),
        )

        self.register_outputs(
            {
                "ingress_nginx": self.ingress_nginx,
                "ingress_nginx_ns": self.ingress_nginx_ns,
                # "socks_proxy": socks_proxy,
                "api_proxy_ns": api_proxy_ns,
                # "ingress_to_proxy": ingress_to_proxy,
            }
        )
