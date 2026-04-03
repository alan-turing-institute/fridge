import pulumi
from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.core.v1 import (
    Namespace,
)
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs
from pulumi_kubernetes.yaml import ConfigFile


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
                # 1. Prometheus Operator (scrapes metrics and serves them to Grafana)
                # 2. Grafana Loki (stores logs)
                # 3. Grafana Alloy (collects data/logs to feed to Loki)
                prometheus_operator = Release(
                    "monitoring-operator",
                    ReleaseArgs(
                        name="kube-prometheus-stack",
                        chart="kube-prometheus-stack",
                        version="82.0.0",
                        repository_opts={
                            "repo": "https://prometheus-community.github.io/helm-charts"
                        },
                        namespace=monitoring_ns.metadata.name,
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
                            "grafana": {
                                "additionalDataSources": [
                                    {
                                        "name": "Loki",
                                        "type": "loki",
                                        "url": "http://grafana-loki:3100",
                                        "access": "proxy",
                                    }
                                ]
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
                        name="grafana-loki",
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
                                "schemaConfig": {
                                    "configs": [
                                        {
                                            "from": "2025-10-24",
                                            "store": "tsdb",
                                            "object_store": "azure",
                                            "schema": "v13",
                                            "index": {
                                                "prefix": "index_",
                                                "period": "24h",
                                            },
                                        }
                                    ]
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
                                        "admin": "loki-admin",
                                    },
                                },
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
                            "chunksCache": {
                                "enabled": False,
                            },
                            "resultsCache": {
                                "enabled": False,
                            },
                            "read": {"replicas": 0},
                            "write": {"replicas": 0},
                            "backend": {"replicas": 0},
                        },
                    ),
                    opts=ResourceOptions.merge(
                        child_opts,
                        ResourceOptions(depends_on=[prometheus_operator]),
                    ),
                )

                alloy_configmap = ConfigFile(
                    "alloy-config",
                    file="k8s/monitoring/alloy_configmap.yaml",
                    opts=ResourceOptions.merge(
                        child_opts,
                        ResourceOptions(depends_on=[prometheus_operator, grafana_loki]),
                    ),
                )

                grafana_alloy = Release(
                    "grafana-alloy",
                    ReleaseArgs(
                        name="grafana-alloy",
                        chart="alloy",
                        version="1.6.2",
                        repository_opts={
                            "repo": "https://grafana.github.io/helm-charts"
                        },
                        namespace=monitoring_ns.metadata.name,
                        create_namespace=False,
                        values={
                            "alloy": {
                                "configMap": {
                                    "create": False,
                                    "name": "alloy-config",
                                    "key": "config",
                                }
                            }
                        },
                    ),
                    opts=ResourceOptions.merge(
                        ResourceOptions(depends_on=[alloy_configmap, grafana_loki]),
                        child_opts,
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
