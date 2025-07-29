from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.core.v1 import (
    Namespace,
    Service,
    ServicePortArgs,
    ServiceSpecArgs,
)
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs
from pulumi_kubernetes.yaml import ConfigFile

from enums import K8sEnvironment


class MonitoringArgs:
    def __init__(self, k8s_environment: K8sEnvironment, argo_server_ns: str):
        self.k8s_environment = k8s_environment
        self.argo_server_ns = argo_server_ns


class Monitoring(ComponentResource):
    def __init__(self, name: str, args: MonitoringArgs, opts=ResourceOptions) -> None:
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
                Release(
                    "monitoring-operator",
                    ReleaseArgs(
                        chart="kube-prometheus-stack",
                        version="75.15.1",
                        repository_opts={
                            "repo": "https://prometheus-community.github.io/helm-charts"
                        },
                        namespace=monitoring_ns.metadata.name,  # Compatibility with Dawn
                        create_namespace=False,
                    ),
                    opts=child_opts,
                )
            case K8sEnvironment.DAWN:
                # The namespace is already created on Dawn
                monitoring_ns = Namespace.get("monitoring-ns", "monitoring-system")

                # Add service for metrics endpoint for Argo Workflows
                argo_workflows_metrics_svc = Service(
                    "argo-workflows-metrics-svc",
                    metadata=ObjectMetaArgs(
                        name="workflow-controller-metrics",
                        namespace=args.argo_server_ns,
                        labels={"app": "workflow-controller"},
                    ),
                    spec=ServiceSpecArgs(
                        cluster_ip=None,
                        ports=[
                            ServicePortArgs(
                                name="metrics",
                                port=9090,
                                protocol="TCP",
                                target_port=9090,
                            ),
                        ],
                        selector={"app": "workflow-controller"},
                    ),
                    opts=child_opts,
                )

                # Add service monitor to allow Prometheus to scrape the metrics
                # Note: Pulumi has no native support for ServiceMonitor,
                # so using ConfigFile to deploy
                ConfigFile(
                    "argo-workflows-service-monitor",
                    file="./k8s/argo_workflows/prometheus.yaml",
                    opts=ResourceOptions(
                        depends_on=[argo_workflows_metrics_svc],
                    ),
                )
