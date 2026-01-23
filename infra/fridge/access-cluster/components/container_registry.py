from string import Template

import pulumi
from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.batch.v1 import (
    Job,
    JobSpecArgs,
)
from pulumi_kubernetes.core.v1 import (
    ConfigMap,
    ContainerArgs,
    EnvVarArgs,
    Namespace,
    PodSpecArgs,
    PodTemplateSpecArgs,
    Secret,
    SecurityContextArgs,
    VolumeArgs,
    VolumeMountArgs,
)
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs, RepositoryOptsArgs
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs
from pulumi_kubernetes.networking.v1 import Ingress
from pulumi_kubernetes.yaml import ConfigGroup

from .storage_classes import StorageClasses


from enums import PodSecurityStandard, TlsEnvironment, tls_issuer_names


class ContainerRegistryArgs:
    def __init__(
        self,
        config: pulumi.config.Config,
        storage_classes: StorageClasses,
        tls_environment: TlsEnvironment,
    ) -> None:
        self.config = config
        self.tls_environment = tls_environment
        self.storage_classes = storage_classes


class ContainerRegistry(ComponentResource):
    def __init__(
        self,
        name: str,
        args: ContainerRegistryArgs,
        opts: ResourceOptions | None = None,
    ):
        super().__init__("fridge:ContainerRegistry", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        self.harbor_ns = Namespace(
            "harbor-ns",
            metadata=ObjectMetaArgs(
                name="harbor",
                labels={} | PodSecurityStandard.RESTRICTED.value,
            ),
            opts=child_opts,
        )

        self.harbor_fqdn = ".".join(
            (
                args.config.require("harbor_fqdn_prefix"),
                args.config.require("base_fqdn"),
            )
        )

        self.harbor_external_url = f"https://{self.harbor_fqdn}"
        self.harbor_storage_settings = {
            "storageClass": args.storage_classes.standard_storage_name,
            "accessMode": "ReadWriteMany"
            if args.storage_classes.standard_supports_rwm
            else "ReadWriteOnce",
        }

        self.harbor = Release(
            "harbor",
            ReleaseArgs(
                chart="harbor",
                namespace="harbor",
                version="1.17.1",
                repository_opts=RepositoryOptsArgs(
                    repo="https://helm.goharbor.io",
                ),
                values={
                    "expose": {
                        "clusterIP": {
                            "staticClusterIP": args.config.require("harbor_ip"),
                        },
                        "type": "clusterIP",
                        "tls": {
                            "enabled": False,
                            "certSource": "none",
                        },
                    },
                    "externalURL": self.harbor_external_url,
                    "harborAdminPassword": args.config.require_secret(
                        "harbor_admin_password"
                    ),
                    "persistence": {
                        "persistentVolumeClaim": {
                            "registry": self.harbor_storage_settings,
                            "jobservice": {
                                "jobLog": self.harbor_storage_settings,
                            },
                        },
                    },
                },
            ),
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[self.harbor_ns]),
            ),
        )

        self.harbor_ingress = Ingress(
            "harbor-ingress",
            metadata=ObjectMetaArgs(
                name="harbor-ingress",
                namespace=self.harbor_ns.metadata.name,
                annotations={
                    "nginx.ingress.kubernetes.io/force-ssl-redirect": "true",
                    "nginx.ingress.kubernetes.io/proxy-body-size": "0",
                    "cert-manager.io/cluster-issuer": tls_issuer_names[
                        args.tls_environment
                    ],
                },
            ),
            spec={
                "ingress_class_name": "nginx",
                "tls": [
                    {
                        "hosts": [
                            self.harbor_fqdn,
                        ],
                        "secret_name": "harbor-ingress-tls",
                    }
                ],
                "rules": [
                    {
                        "host": self.harbor_fqdn,
                        "http": {
                            "paths": [
                                {
                                    "path": "/",
                                    "path_type": "Prefix",
                                    "backend": {
                                        "service": {
                                            "name": "harbor",
                                            "port": {
                                                "number": 80,
                                            },
                                        }
                                    },
                                }
                            ]
                        },
                    }
                ],
            },
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(
                    depends_on=[
                        self.harbor,
                    ]
                ),
            ),
        )

        # Create a daemonset to skip TLS verification for the harbor registry
        # This is needed while using staging/self-signed certificates for Harbor
        # A daemonset is used to run the configuration on all nodes in the cluster

        self.containerd_config_ns = Namespace(
            "containerd-config-ns",
            metadata=ObjectMetaArgs(
                name="containerd-config",
                labels={} | PodSecurityStandard.PRIVILEGED.value,
            ),
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(
                    depends_on=[self.harbor],
                ),
            ),
        )

        self.skip_harbor_tls = Template(
            open("k8s/harbor/skip_harbor_tls_verification.yaml", "r").read()
        ).substitute(
            namespace="containerd-config",
            harbor_fqdn=self.harbor_fqdn,
            harbor_url=self.harbor_external_url,
            harbor_ip=args.config.require("harbor_ip"),
            harbor_internal_url="http://" + args.config.require("harbor_ip"),
        )

        self.configure_containerd_daemonset = ConfigGroup(
            "configure-containerd-daemon",
            yaml=[self.skip_harbor_tls],
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(
                    depends_on=[self.harbor],
                ),
            ),
        )

        with open("components/scripts/harbor_config.sh", "r") as f:
            config_script = f.read()

        harbor_config_script = ConfigMap(
            "harbor-config-script",
            metadata=ObjectMetaArgs(
                name="harbor-config-script",
                namespace=self.harbor_ns.metadata.name,
            ),
            data={"configure_harbor.sh": config_script},
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[self.harbor]),
            ),
        )

        harbor_admin_secret = Secret(
            "harbor-admin-secret",
            metadata=ObjectMetaArgs(
                name="harbor-admin-credentials",
                namespace=self.harbor_ns.metadata.name,
            ),
            type="Opaque",
            string_data={
                "username": "admin",
                "password": args.config.require_secret("harbor_admin_password"),
            },
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[self.harbor]),
            ),
        )

        self.configure_harbor = Job(
            "configure-harbor",
            metadata=ObjectMetaArgs(
                name="harbor-config-job",
                namespace=self.harbor_ns.metadata.name,
                labels={"app": "harbor-config-job"},
            ),
            spec=JobSpecArgs(
                backoff_limit=2,
                template=PodTemplateSpecArgs(
                    spec=PodSpecArgs(
                        containers=[
                            ContainerArgs(
                                name="harbor-config-job",
                                image="badouralix/curl-jq:latest",
                                env=[
                                    EnvVarArgs(
                                        name="HARBOR_URL",
                                        value="harbor.harbor.svc.cluster.local",
                                    ),
                                ],
                                command=["/bin/sh", "/scripts/configure_harbor.sh"],
                                volume_mounts=[
                                    VolumeMountArgs(
                                        name="harbor-credentials",
                                        mount_path="/run/secrets/harbor",
                                        read_only=True,
                                    ),
                                    VolumeMountArgs(
                                        name="harbor-config-script-volume",
                                        mount_path="/scripts",
                                        read_only=True,
                                    ),
                                ],
                                security_context=SecurityContextArgs(
                                    allow_privilege_escalation=False,
                                    capabilities={"drop": ["ALL"]},
                                    run_as_group=1000,
                                    run_as_non_root=True,
                                    run_as_user=1000,
                                    seccomp_profile={"type": "RuntimeDefault"},
                                ),
                            ),
                        ],
                        volumes=[
                            VolumeArgs(
                                name="harbor-credentials",
                                secret={
                                    "secret_name": harbor_admin_secret.metadata.name,
                                },
                            ),
                            VolumeArgs(
                                name="harbor-config-script-volume",
                                config_map={
                                    "name": harbor_config_script.metadata.name,
                                },
                            ),
                        ],
                        restart_policy="Never",
                    )
                ),
            ),
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[self.harbor_ns, harbor_config_script]),
            ),
        )

        self.register_outputs(
            {
                "configure_containerd_daemonset": self.configure_containerd_daemonset,
                "containerd_config_ns": self.containerd_config_ns,
                "harbor": self.harbor,
                "harbor_ingress": self.harbor_ingress,
                "harbor_ns": self.harbor_ns,
            }
        )
