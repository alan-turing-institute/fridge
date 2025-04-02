from pulumi_kubernetes.helm.v3 import Chart, ChartOpts, FetchOpts


cilium = Chart(
    "cilium",
    ChartOpts(
        namespace="kube-system",
        chart="cilium",
        version="1.16.7",
        fetch_opts=FetchOpts(
            repo="https://helm.cilium.io",
        ),
        values={
            "operator": {
                "replicas": 1
            }
        },
    ),
)
