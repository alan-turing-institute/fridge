from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.core.v1 import Namespace
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs

from enums import K8sEnvironment, PodSecurityStandard


class IngressArgs:
    def __init__(self, k8s_environment: K8sEnvironment):
        self.k8s_environment = k8s_environment


class Ingress(ComponentResource):
    def __init__(self, name: str, args: IngressArgs, opts: ResourceOptions = None):
        super().__init__("fridge:k8s:Ingress", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        k8s_environment = args.k8s_environment

        match k8s_environment:
            case K8sEnvironment.AKS | K8sEnvironment.K3S:
                ingress_nginx_ns = Namespace(
                    "ingress-nginx-ns",
                    metadata=ObjectMetaArgs(
                        name="ingress-nginx",
                        labels={} | PodSecurityStandard.RESTRICTED.value,
                    ),
                    opts=child_opts,
                )
            case K8sEnvironment.DAWN:
                # Dawn specific configuration
                ingress_nginx_ns = Namespace.get("ingress-nginx-ns", "ingress-nginx")
                ingress_nginx = Release.get("ingress-nginx", "ingress-nginx")

        match k8s_environment:
            case K8sEnvironment.K3S:
                ingress_nginx = Release(
                    "ingress-nginx",
                    ReleaseArgs(
                        chart="ingress-nginx",
                        version="4.13.2",
                        repository_opts={
                            "repo": "https://kubernetes.github.io/ingress-nginx"
                        },
                        namespace=ingress_nginx_ns.metadata.name,
                        create_namespace=False,
                        values={
                            "controller": {
                                "metrics": {
                                    "enabled": True,
                                    "serviceMonitor": {"enabled": True},
                                }
                            },
                        },
                    ),
                    opts=ResourceOptions.merge(
                        child_opts, ResourceOptions(depends_on=ingress_nginx_ns)
                    ),
                )
            case K8sEnvironment.AKS:
                ingress_nginx = Release(
                    "ingress-nginx",
                    ReleaseArgs(
                        chart="ingress-nginx",
                        version="4.13.2",
                        repository_opts={
                            "repo": "https://kubernetes.github.io/ingress-nginx"
                        },
                        namespace=ingress_nginx_ns.metadata.name,
                        create_namespace=False,
                        values={
                            "controller": {
                                "metrics": {
                                    "enabled": True,
                                    "serviceMonitor": {"enabled": True},
                                }
                            },
                        },
                    ),
                    opts=ResourceOptions.merge(
                        child_opts, ResourceOptions(depends_on=ingress_nginx_ns)
                    ),
                )

        self.register_outputs(
            {"ingress_nginx_ns": ingress_nginx_ns, "ingress_nginx": ingress_nginx}
        )
