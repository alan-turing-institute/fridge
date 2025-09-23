import pulumi
from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs


class DualClusterArgs:
    def __init__(
        self,
        access_kubeconfig: pulumi.Output[str],
        private_kubeconfig: pulumi.Output[str],
    ):
        self.access_kubeconfig = access_kubeconfig
        self.private_kubeconfig = private_kubeconfig


class DualCluster(ComponentResource):
    def __init__(self, name: str, args: DualClusterArgs, opts: ResourceOptions = None):
        super().__init__("custom:resource:DualCluster", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        # Deploy something to both clusters to verify connectivity

        access_cluster_ingress = Release(
            "access-cluster-ingress",
            ReleaseArgs(
                chart="nginx-ingress",
                repository_opts={"repo": "https://kubernetes.github.io/ingress-nginx"},
                namespace="default",
                values={
                    "controller": {
                        "replicaCount": 2,
                        "service": {"type": "LoadBalancer"},
                    }
                },
                kubeconfig=args.access_kubeconfig,
            ),
            opts=child_opts,
        )

        self.register_outputs({})
