from pulumi_kubernetes.core.v1 import Namespace

from pulumi_kubernetes.helm.v3 import Chart, ChartOpts, FetchOpts

nginx_ingress_namespace = Namespace("ingress")

nginx_ingress = Chart(
    "ingress-nginx",
    ChartOpts(
        namespace=nginx_ingress_namespace.metadata.name,
        chart="ingress-nginx",
        version="4.12.1",
        fetch_opts=FetchOpts(
            repo="https://kubernetes.github.io/ingress-nginx",
        ),
    ),
)
