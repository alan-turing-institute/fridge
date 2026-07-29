import pulumi
from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.core.v1 import (
    Namespace,
)
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs
from pulumi_kubernetes.yaml import ConfigFile


from enums import K8sEnvironment, SoftwareVersion


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

        self.monitoring_ns = Namespace(
            "monitoring-system",
            metadata=ObjectMetaArgs(
                name="monitoring-system",
                labels={"name": "monitoring-system"},
            ),
            opts=child_opts,
        )

        self.prometheus_operator = Release(
            "monitoring-operator",
            ReleaseArgs(
                name="kube-prometheus-stack",
                chart="kube-prometheus-stack",
                version=SoftwareVersion.KUBE_PROMETHEUS_STACK.value,
                repository_opts={
                    "repo": "https://prometheus-community.github.io/helm-charts"
                },
                namespace=self.monitoring_ns.metadata.name,
                create_namespace=False,
                values={
                    "alertmanager": {
                        "alertmanagerSpec": {
                            "retention": "168h",  # 7 days
                            "storage": {
                                "volumeClaimTemplate": {
                                    "spec": {
                                        "accessMode": ["ReadWriteOnce"],
                                        "resources": {"requests": {"storage": "3Gi"}},
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
                        # revisit specs for prod
                        "prometheusSpec": {
                            "retention": "4d",
                            "retentionSize": "2GiB",
                            "storageSpec": {
                                "volumeClaimTemplate": {
                                    "spec": {
                                        "accessModes": ["ReadWriteOnce"],
                                        "resources": {"requests": {"storage": "3Gi"}},
                                    }
                                }
                            },
                        }
                    },
                },
            ),
            opts=child_opts,
        )

        match args.k8s_environment:
            case K8sEnvironment.AKS:

                # Start by deploying the monitoring stack for AKS
                # 1. Prometheus Operator (scrapes metrics and serves them to Grafana)
                # 2. Grafana Loki (stores logs)
                # 3. Grafana Alloy (collects data/logs to feed to Loki)

                loki_values = {
                    "loki": {
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
                        },
                    }
                }

            case K8sEnvironment.DAWN:
                loki_values = {
                    "loki": {
                        "schemaConfig": {
                            "configs": [
                                {
                                    "from": "2025-10-24",
                                    "store": "tsdb",
                                    "object_store": "filesystem",
                                    "schema": "v13",
                                    "index": {
                                        "prefix": "index_",
                                        "period": "24h",
                                    },
                                }
                            ]
                        },
                        "storage": {
                            "type": "filesystem",
                        },
                    }
                }

        self.grafana_loki = Release(
            "grafana-loki",
            ReleaseArgs(
                name="grafana-loki",
                chart="loki",
                version=SoftwareVersion.GRAFANA_LOKI.value,
                repository_opts={"repo": "https://grafana.github.io/helm-charts"},
                namespace=self.monitoring_ns.metadata.name,
                create_namespace=False,
                values_yaml_file="k8s/monitoring/loki-values.yaml",
                values=loki_values,
            ),
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[self.prometheus_operator]),
            ),
        )

        alloy_configmap = ConfigFile(
            "alloy-config",
            file="k8s/monitoring/alloy_configmap.yaml",
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(
                    depends_on=[self.prometheus_operator, self.grafana_loki]
                ),
            ),
        )

        self.grafana_alloy = Release(
            "grafana-alloy",
            ReleaseArgs(
                name="grafana-alloy",
                chart="alloy",
                version=SoftwareVersion.GRAFANA_ALLOY.value,
                repository_opts={"repo": "https://grafana.github.io/helm-charts"},
                namespace=self.monitoring_ns.metadata.name,
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
                ResourceOptions(depends_on=[alloy_configmap, self.grafana_loki]),
                child_opts,
            ),
        )

        self.register_outputs(
            {
                "namespace": self.monitoring_ns.metadata.name,
                "grafana_loki": self.grafana_loki,
                "prometheus_operator": self.prometheus_operator,
                "grafana_alloy": self.grafana_alloy,
            }
        )
