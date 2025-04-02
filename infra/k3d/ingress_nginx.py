from pulumi_kubernetes.core.v1 import Namespace

from pulumi_kubernetes.helm.v3 import Chart, ChartOpts, FetchOpts
from pulumi_crds.cilium.v2 import CiliumNetworkPolicy

nginx_ingress_namespace = Namespace(
    "ingress",
    metadata={
        "name": "ingress",
        "annotations": {
            "pod-security.kubernetes.io/enforce": "restricted",
            "pod-security.kubernetes.io/enforce-version": "latest"
        }
    }
)

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

default_deny_policy = CiliumNetworkPolicy(
    "default-deny",
    metadata={
        "namespace": nginx_ingress_namespace.metadata.name,
    },
    spec={
        "endpoint_selector": {},
        "ingress": [],
        "egress": []
    }
)
