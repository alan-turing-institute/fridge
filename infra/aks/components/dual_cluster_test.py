import pulumi
from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes import Provider
from pulumi_kubernetes.core.v1 import (
    Namespace,
    PodSpecArgs,
    PodTemplateSpecArgs,
    ContainerArgs,
    ContainerPortArgs,
)
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs
from pulumi_kubernetes.networking.v1 import (
    Ingress,
    IngressSpecArgs,
    IngressRuleArgs,
    HTTPIngressRuleValueArgs,
    HTTPIngressPathArgs,
    IngressBackendArgs,
    IngressServiceBackendArgs,
    ServiceBackendPortArgs,
)

from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs
from pulumi_kubernetes.apps.v1 import Deployment, DeploymentSpecArgs
from pulumi_kubernetes.meta.v1 import LabelSelectorArgs


class DualClusterArgs:
    def __init__(
        self,
        access_kubeconfig: Provider,
        private_kubeconfig: Provider,
    ):
        self.access_kubeconfig = access_kubeconfig
        self.private_kubeconfig = private_kubeconfig


class DualCluster(ComponentResource):
    def __init__(self, name: str, args: DualClusterArgs, opts: ResourceOptions = None):
        super().__init__("custom:resource:DualCluster", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        # Deploy something to both clusters to verify connectivity

        ingress_nginx_ns = Namespace(
            "ingress-nginx-ns",
            metadata=ObjectMetaArgs(
                name="ingress-nginx",
                labels={},  # | PodSecurityStandard.RESTRICTED.value,
            ),
            opts=ResourceOptions.merge(
                child_opts, ResourceOptions(provider=args.access_kubeconfig)
            ),
        )

        # ingress_nginx_private = Namespace(
        #     "ingress-nginx-private-ns",
        #     metadata=ObjectMetaArgs(
        #         name="ingress-nginx",
        #         labels={},  # | PodSecurityStandard.RESTRICTED.value,
        #     ),
        #     opts=ResourceOptions.merge(
        #         child_opts,
        #         ResourceOptions(
        #             provider=args.private_kubeconfig
        #         ),
        #     ),
        # )

        ingress_nginx = Release(
            "ingress-nginx",
            ReleaseArgs(
                chart="ingress-nginx",
                version="4.13.2",
                repository_opts={"repo": "https://kubernetes.github.io/ingress-nginx"},
                namespace=ingress_nginx_ns.metadata.name,
                create_namespace=False,
                values={
                    "controller": {
                        "nodeSelector": {"kubernetes.io/os": "linux"},
                        "service": {
                            "externalTrafficPolicy": "Local",
                        },
                    }
                },
            ),
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(
                    depends_on=ingress_nginx_ns, provider=args.access_kubeconfig
                ),
            ),
        )

        socks_proxy_ns = Namespace(
            "socks-proxy-ns",
            metadata=ObjectMetaArgs(
                name="socks-proxy", labels={}  # | PodSecurityStandard.RESTRICTED.value,
            ),
            opts=ResourceOptions.merge(
                child_opts, ResourceOptions(provider=args.access_kubeconfig)
            ),
        )

        socks_proxy = Deployment(
            "socks-proxy",
            metadata=ObjectMetaArgs(
                namespace=socks_proxy_ns.metadata.name,
            ),
            spec=DeploymentSpecArgs(
                selector=LabelSelectorArgs(
                    match_labels={"app": "socks-proxy"},
                ),
                replicas=1,
                template=PodTemplateSpecArgs(
                    metadata=ObjectMetaArgs(
                        labels={"app": "socks-proxy"},
                    ),
                    spec=PodSpecArgs(
                        containers=[
                            ContainerArgs(
                                name="socks-proxy",
                                image="serjs/go-socks5-proxy:latest",
                                ports=[ContainerPortArgs(container_port=1080)],
                            )
                        ]
                    ),
                ),
            ),
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(
                    depends_on=ingress_nginx, provider=args.access_kubeconfig
                ),
            ),
        )

        # ingress_to_proxy = Ingress(
        #     "ingress-to-proxy",
        #     metadata=ObjectMetaArgs(
        #         namespace=socks_proxy_ns.metadata.name,
        #     ),
        #     spec=IngressSpecArgs(
        #         rules=[
        #             IngressRuleArgs(
        #                 #host="socks-proxy.fridge.internal",
        #                 http=HTTPIngressRuleValueArgs(
        #                     paths=[
        #                         HTTPIngressPathArgs(
        #                             path="/",
        #                             path_type="Prefix",
        #                             backend=IngressBackendArgs(
        #                                 service=IngressServiceBackendArgs(
        #                                     name=socks_proxy.metadata.name,
        #                                     port=ServiceBackendPortArgs(number=1080),
        #                                 )
        #                             ),
        #                         )
        #                     ]
        #                 ),
        #             )
        #         ]
        #     ),
        #     opts=ResourceOptions.merge(
        #         child_opts,
        #         ResourceOptions(
        #             depends_on=socks_proxy, provider=args.access_kubeconfig
        #         ),
        #     ),
        # )

        self.register_outputs(
            {
                "ingress_nginx": ingress_nginx,
                "ingress_nginx_ns": ingress_nginx_ns,
                "socks_proxy": socks_proxy,
                "socks_proxy_ns": socks_proxy_ns,
                # "ingress_to_proxy": ingress_to_proxy,
            }
        )
