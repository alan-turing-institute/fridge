import pulumi
from pulumi import ComponentResource, Input, Output, ResourceOptions
from pulumi_kubernetes.core.v1 import Namespace, Secret
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs
from pulumi_kubernetes.yaml import ConfigFile, ConfigGroup

from enums import K8sEnvironment, PodSecurityStandard, SoftwareVersion

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

TEAMS_WEBHOOK_SECRET_NAME = "alertmanager-teams-webhook"


def teams_alertmanager_config() -> dict:
    """Alertmanager routing that sends alerts to a Microsoft Teams Workflows webhook.

    Helm merges this into the chart's default config, so the default inhibit rules
    and templates are kept, while the route's `routes` and `receivers` are replaced.
    """
    return {
        "route": {
            "receiver": "teams",
            "routes": [
                # Watchdog always fires, to show the alerting pipeline is working. It
                # isn't worth a message, but could feed an external heartbeat check
                {"receiver": "null", "matchers": ['alertname = "Watchdog"']},
                # InfoInhibitor only exists to suppress info alerts
                {"receiver": "null", "matchers": ['alertname = "InfoInhibitor"']},
                # Info alerts are still visible in Alertmanager and Grafana
                {"receiver": "null", "matchers": ['severity = "info"']},
            ],
        },
        "receivers": [
            {"name": "null"},
            {
                "name": "teams",
                "msteamsv2_configs": [
                    {
                        "webhook_url_file": f"/etc/alertmanager/secrets/{TEAMS_WEBHOOK_SECRET_NAME}/url",
                        "send_resolved": True,
                    }
                ],
            },
        ],
    }


class MonitoringConfig:
    """The stack's `monitoring` configuration object.

    Network policies also need the Teams webhook URL, so this is read once in
    __main__ and passed to both components.
    """

    def __init__(self, config: pulumi.config.Config):
        # The plain values are only used to check which keys are set, so that missing
        # keys give a clear error and optional ones can switch features on and off.
        # The values themselves are read from the secret copy.
        # Unset fields can appear as the field descriptions from Pulumi.yaml (the
        # object's default), so only count strings as set
        settings = config.get_object("monitoring") or {}

        def is_set(key: str) -> bool:
            value = settings.get(key)
            return isinstance(value, str) and value != ""

        if not is_set("grafana_admin_password"):
            raise ValueError(
                "Missing required configuration value monitoring.grafana_admin_password. "
                "Set it with: pulumi config set --secret --path "
                "monitoring.grafana_admin_password <value>"
            )
        secret_settings = config.require_secret_object("monitoring")

        self.grafana_admin_password: Output[str] = secret_settings.apply(
            lambda s: s["grafana_admin_password"]
        )
        self.teams_webhook_url: Output[str] | None = (
            secret_settings.apply(lambda s: s["teams_webhook_url"])
            if is_set("teams_webhook_url")
            else None
        )


class MonitoringArgs:
    def __init__(
        self,
        settings: MonitoringConfig,
        k8s_environment: K8sEnvironment,
        storage_class_name: Input[str],
    ):
        self.settings = settings
        self.k8s_environment = k8s_environment
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

        alertmanager_values: dict = {
            "alertmanagerSpec": {
                "retention": "168h",  # 7 days
                "storage": volume_claim("1Gi"),
            }
        }
        release_depends_on = []

        # Send alerts to a Microsoft Teams channel if a Workflows webhook is configured.
        # Otherwise keep the chart's default, which sends them nowhere
        teams_webhook_url = args.settings.teams_webhook_url
        if teams_webhook_url is not None:
            self.teams_webhook_secret = Secret(
                "alertmanager-teams-webhook",
                metadata=ObjectMetaArgs(
                    name=TEAMS_WEBHOOK_SECRET_NAME,
                    namespace=self.monitoring_ns.metadata.name,
                ),
                string_data={"url": teams_webhook_url},
                opts=child_opts,
            )
            release_depends_on.append(self.teams_webhook_secret)
            alertmanager_values["alertmanagerSpec"]["secrets"] = [
                TEAMS_WEBHOOK_SECRET_NAME
            ]
            alertmanager_values["config"] = teams_alertmanager_config()

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
                    "alertmanager": alertmanager_values,
                    "grafana": {
                        "adminPassword": args.settings.grafana_admin_password,
                        "testFramework": {"enabled": False},
                        # By default the dashboard and datasource sidecars can read
                        # Secrets and ConfigMaps in every namespace. Limit them to this
                        # namespace, which holds all the stack's dashboards
                        "rbac": {"namespaced": True},
                        # (Pulumi drops None values, so this has to name the
                        # namespace to override the stack's default of ALL)
                        "sidecar": {
                            "dashboards": {
                                "searchNamespace": self.monitoring_ns.metadata.name
                            }
                        },
                        # Don't try to contact grafana.com (update checks, usage
                        # statistics, news feed, downloading the default plugins).
                        # The network policies block it anyway
                        "grafana.ini": {
                            "analytics": {
                                "check_for_updates": False,
                                "check_for_plugin_updates": False,
                                "reporting_enabled": False,
                            },
                            "news": {"news_feed_enabled": False},
                            "plugins": {"preinstall_disabled": True},
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
                            # Added to every alert, so notifications say which
                            # deployment they came from
                            "externalLabels": {"cluster": pulumi.get_stack()},
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
            opts=ResourceOptions.merge(
                child_opts, ResourceOptions(depends_on=release_depends_on)
            ),
        )

        # These need the CRDs installed by the chart
        after_stack_opts = ResourceOptions.merge(
            child_opts,
            ResourceOptions(depends_on=[self.kube_prometheus_stack]),
        )

        self.alerting_rules = ConfigFile(
            "fridge-alerting-rules",
            file="./k8s/monitoring/alerting-rules.yaml",
            opts=after_stack_opts,
        )

        scrape_target_files = ["./k8s/monitoring/scrape-targets.yaml"]
        if args.k8s_environment in (K8sEnvironment.DAWN, K8sEnvironment.ZENITH):
            scrape_target_files.append("./k8s/monitoring/longhorn.yaml")

        self.scrape_targets = ConfigGroup(
            "fridge-scrape-targets",
            files=scrape_target_files,
            opts=after_stack_opts,
        )

        self.register_outputs(
            {
                "namespace": self.monitoring_ns.metadata.name,
                "kube_prometheus_stack": self.kube_prometheus_stack,
                "alerting_rules": self.alerting_rules,
                "scrape_targets": self.scrape_targets,
            }
        )
