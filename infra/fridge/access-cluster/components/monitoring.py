import pulumi
from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.core.v1 import (
    Namespace,
    Service,
    ServicePortArgs,
    ServiceSpecArgs,
)
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs


from enums import K8sEnvironment


class MonitoringArgs:
    def __init__(self, config: pulumi.config.Config, k8s_environment: K8sEnvironment):
        self.config = config
        self.k8s_environment = k8s_environment


class Monitoring(ComponentResource):
    def __init__(
        self, name: str, args: MonitoringArgs, opts: ResourceOptions | None = None
    ) -> None:
        super().__init__("fridge:k8s:Monitoring", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        match args.k8s_environment:
            case K8sEnvironment.AKS:

                monitoring_ns = Namespace(
                    "monitoring-system",
                    metadata=ObjectMetaArgs(
                        name="monitoring-system",
                        labels={"name": "monitoring-system"},
                    ),
                    opts=child_opts,
                )
                # Start by deploying the monitoring stack for AKS
                # 1. Prometheus Operator
                # 2. Grafana
                prometheus_operator = Release(
                    "monitoring-operator",
                    ReleaseArgs(
                        chart="kube-prometheus-stack",
                        version="82.0.0",
                        repository_opts={
                            "repo": "https://prometheus-community.github.io/helm-charts"
                        },
                        namespace=monitoring_ns.metadata.name,
                        create_namespace=False,
                    ),
                    opts=child_opts,
                )

                grafana_loki = Release(
                    "grafana-loki",
                    ReleaseArgs(
                        chart="loki",
                        version="6.53.0",
                        repository_opts={
                            "repo": "https://grafana.github.io/helm-charts"
                        },
                        namespace=monitoring_ns.metadata.name,
                        create_namespace=False,
                        values={
                            "deploymentMode": "SingleBinary",
                            "loki": {
                                "auth_enabled": False,
                                "commonConfig": {
                                    "replication_factor": 1,
                                },
                                "singleBinary": {
                                    "replicas": 1,
                                    "resources": {
                                        "requests": {"cpu": "500m", "memory": "512Mi"}
                                    },
                                    "persistence": {
                                        "enabled": True,
                                        "size": "10Gi",
                                        "storageClassName": "default",
                                    },
                                },
                                "storage": {
                                    "type": "azure",
                                    "azure": {
                                        "connectionString": args.config.require(
                                            "azure_storage_connection_string"
                                        ),
                                    },
                                    "bucketNames": {
                                        "chunks": "loki-chunks",
                                        "ruler": "loki-ruler",
                                    },
                                },
                                "useTestSchema": True,
                            },
                            "chunksCache": {
                                "enabled": False,
                            },
                            "resultsCache": {
                                "enabled": False,
                            },
                        },
                    ),
                    opts=ResourceOptions.merge(
                        child_opts,
                        ResourceOptions(depends_on=[prometheus_operator]),
                    ),
                )
            case K8sEnvironment.DAWN:
                # The namespace is already created on Dawn
                monitoring_ns = Namespace.get("monitoring-ns", "monitoring-system")
                prometheus_operator = Release.get(
                    "monitoring-operator", "monitoring-system/kube-prometheus-stack"
                )
                grafana_loki = Release.get(
                    "grafana-loki", "monitoring-system/loki-stack"
                )

            case K8sEnvironment.K3S:
                monitoring_ns = Namespace(
                    "monitoring-system",
                    metadata=ObjectMetaArgs(
                        name="monitoring-system",
                        labels={"name": "monitoring-system"},
                    ),
                    opts=child_opts,
                )

                # Start by deploying the monitoring stack
                # 1. Prometheus Operator
                # 2. Grafana Loki
                prometheus_operator = Release(
                    "monitoring-operator",
                    ReleaseArgs(
                        chart="kube-prometheus-stack",
                        version="81.6.3",
                        repository_opts={
                            "repo": "https://prometheus-community.github.io/helm-charts"
                        },
                        namespace=monitoring_ns.metadata.name,  # Compatibility with Dawn
                        create_namespace=False,
                        values={
                            "alertmanager": {
                                "alertmanagerSpec": {
                                    "retention": "168h",
                                    "storage": {
                                        "volumeClaimTemplate": {
                                            "spec": {
                                                "accessMode": ["ReadWriteOnce"],
                                                "resources": {
                                                    "requests": {"storage": "3Gi"}
                                                },
                                            }
                                        }
                                    },
                                }
                            },
                            "prometheus": {
                                "prometheusSpec": {
                                    "retention": "4d",
                                    "retentionSize": "2GiB",
                                    "storageSpec": {
                                        "volumeClaimTemplate": {
                                            "spec": {
                                                "accessModes": ["ReadWriteOnce"],
                                                "resources": {
                                                    "requests": {"storage": "3Gi"}
                                                },
                                            }
                                        }
                                    },
                                }
                            },
                        },
                    ),
                    opts=child_opts,
                )
                grafana_loki = Release(
                    "grafana-loki",
                    ReleaseArgs(
                        chart="loki-stack",
                        version="6.53.0",
                        repository_opts={
                            "repo": "https://grafana.github.io/helm-charts"
                        },
                        namespace=monitoring_ns.metadata.name,
                        create_namespace=False,
                    ),
                    opts=child_opts,
                )

        self.register_outputs(
            {
                "namespace": monitoring_ns.metadata.name,
                "grafana_loki": grafana_loki,
                "prometheus_operator": prometheus_operator,
            }
        )
