from pulumi import ComponentResource, Output, ResourceOptions
from pulumi_kubernetes.core.v1 import Namespace, Service
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs

from enums import K8sEnvironment, PodSecurityStandard


class IngressArgs:
    def __init__(self, k8s_environment: K8sEnvironment):
        self.k8s_environment = k8s_environment


class Ingress(ComponentResource):
    def __init__(
        self, name: str, args: IngressArgs, opts: ResourceOptions | None = None
    ):
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
                                "nodeSelector": {"kubernetes.io/os": "linux"},
                                "service": {
                                    "externalTrafficPolicy": "Local",
                                },
                            }
                        },
                    ),
                    opts=ResourceOptions.merge(
                        child_opts, ResourceOptions(depends_on=ingress_nginx_ns)
                    ),
                )

            case K8sEnvironment.OKE:

                # Ingress NGINX (ingress provider)
                ingress_nginx_ns = Namespace(
                    "ingress-nginx-ns",
                    metadata=ObjectMetaArgs(
                        name="ingress-nginx",
                        labels={} | PodSecurityStandard.RESTRICTED.value,
                    ),
                )

                ingress_nginx = Release(
                    "ingress-nginx",
                    args=ReleaseArgs(
                        name="ingress-nginx",
                        chart="oci://ghcr.io/nginx/charts/nginx-ingress",
                        create_namespace=False,
                        namespace=ingress_nginx_ns.metadata.name,
                        version="2.3.0",
                        replace=True,
                        values={
                            "controller": {
                                "name": "nginx-ingress-controller",
                                "service": {
                                    "name": "nginx-ingress-controller",
                                    "annotations": {
                                        "oci.oraclecloud.com/load-balancer-type": "lb"
                                    },
                                },
                            },
                        },
                    ),
                    opts=ResourceOptions(depends_on=[ingress_nginx_ns])
                )

            case K8sEnvironment.DAWN:
                # Dawn specific configuration
                ingress_nginx_ns = Namespace.get("ingress-nginx-ns", "ingress-nginx")
                ingress_nginx = Release.get("ingress-nginx", "ingress-nginx")

        controller_name = Output.concat(
            ingress_nginx_ns.metadata.name,
            "/",
            ingress_nginx.status.name,
            "-controller",
        )

        ingress_service = Service.get(
            "ingress-nginx-controller-service",
            controller_name,
        )

        self.ingress_ip = ingress_service.status.load_balancer.ingress[0].ip
        self.ingress_ports = ingress_service.spec.ports.apply(
            lambda ports: [item.port for item in ports]
        )

        self.register_outputs(
            {"ingress_nginx_ns": ingress_nginx_ns, "ingress_nginx": ingress_nginx}
        )
