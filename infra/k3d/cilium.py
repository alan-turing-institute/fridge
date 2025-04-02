from pulumi import ResourceOptions, ResourceTransformationArgs, ResourceTransformationResult
from pulumi_kubernetes.helm.v3 import Chart, ChartOpts, FetchOpts


def ignore_changes(args: ResourceTransformationArgs):
    if args.type_ == "kubernetes:core/v1:Secret":
        return ResourceTransformationResult(
            props=args.props,
            opts=ResourceOptions.merge(args.opts, ResourceOptions(
                ignore_changes=[
                    "data",
                ],
            )))


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
    opts=ResourceOptions(
        transformations=[ignore_changes],
    )
)
