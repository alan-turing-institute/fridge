import pulumi
from pulumi import ComponentResource, Input, ResourceOptions
from pulumi_kubernetes.core.v1 import Namespace
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs
from pulumi_kubernetes.yaml import ConfigFile

from enums import PodSecurityStandard, SoftwareVersion

# The kube-state-metrics chart's default collectors, without secrets
KUBE_STATE_METRICS_COLLECTORS = [
    "certificatesigningrequests",
    "configmaps",
    "cronjobs",
    "daemonsets",
    "deployments",
    "endpointslices",
    "horizontalpodautoscalers",
    "ingresses",
    "jobs",
    "leases",
    "limitranges",
    "mutatingwebhookconfigurations",
    "namespaces",
    "networkpolicies",
    "nodes",
    "persistentvolumeclaims",
    "persistentvolumes",
    "poddisruptionbudgets",
    "pods",
    "replicasets",
    "replicationcontrollers",
    "resourcequotas",
    "services",
    "statefulsets",
    "storageclasses",
    "validatingwebhookconfigurations",
    "volumeattachments",
]


class MonitoringArgs:
    def __init__(
        self,
        config: pulumi.config.Config,
        storage_class_name: Input[str],
    ):
        self.config = config
        self.storage_class_name = storage_class_name


class Monitoring(ComponentResource):
    def __init__(
        self, name: str, args: MonitoringArgs, opts: ResourceOptions | None = None
    ) -> None:
        super().__init__("fridge:k8s:Monitoring", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        # node-exporter needs host networking, host PID and host paths,
        # so the namespace cannot use the restricted standard
        self.monitoring_ns = Namespace(
            "monitoring-system-ns",
            metadata=ObjectMetaArgs(
                name="monitoring-system",
                labels={} | PodSecurityStandard.PRIVILEGED.value,
            ),
            opts=child_opts,
        )

        def volume_claim(size: str) -> dict:
            return {
                "volumeClaimTemplate": {
                    "spec": {
                        "storageClassName": args.storage_class_name,
                        "accessModes": ["ReadWriteOnce"],
                        "resources": {"requests": {"storage": size}},
                    }
                }
            }

        self.kube_prometheus_stack = Release(
            "kube-prometheus-stack",
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
                            "storage": volume_claim("1Gi"),
                        }
                    },
                    "grafana": {
                        "adminPassword": args.config.require_secret(
                            "grafana_admin_password"
                        ),
                        "testFramework": {"enabled": False},
                        # By default the dashboard and datasource sidecars can read
                        # Secrets and ConfigMaps in every namespace. Limit them to this
                        # namespace, which holds all the stack's dashboards
                        "rbac": {"namespaced": True},
                        "sidecar": {"dashboards": {"searchNamespace": None}},
                        # Don't try to contact grafana.com (update checks, usage
                        # statistics, news feed). The network policies block it anyway
                        "grafana.ini": {
                            "analytics": {
                                "check_for_updates": False,
                                "check_for_plugin_updates": False,
                                "reporting_enabled": False,
                            },
                            "news": {"news_feed_enabled": False},
                        },
                    },
                    # The default collector list includes secrets, which gives
                    # kube-state-metrics permission to list (and so read) every Secret
                    # in the cluster. It only exports their names, which we don't need
                    "kube-state-metrics": {"collectors": KUBE_STATE_METRICS_COLLECTORS},
                    "prometheus": {
                        "prometheusSpec": {
                            # Keep retentionSize below the volume size so Prometheus
                            # removes old data before the volume fills up
                            "retention": "15d",
                            "retentionSize": "8GiB",
                            "storageSpec": volume_claim("10Gi"),
                        }
                    },
                    # Control plane components are either managed by the provider (AKS)
                    # or not reachable from pods, so scraping them only produces
                    # permanently firing TargetDown alerts. Cilium replaces kube-proxy
                    "kubeControllerManager": {"enabled": False},
                    "kubeEtcd": {"enabled": False},
                    "kubeProxy": {"enabled": False},
                    "kubeScheduler": {"enabled": False},
                },
            ),
            opts=child_opts,
        )

        self.alerting_rules = ConfigFile(
            "fridge-alerting-rules",
            file="./k8s/monitoring/alerting-rules.yaml",
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[self.kube_prometheus_stack]),
            ),
        )

        self.register_outputs(
            {
                "namespace": self.monitoring_ns.metadata.name,
                "kube_prometheus_stack": self.kube_prometheus_stack,
                "alerting_rules": self.alerting_rules,
            }
        )
