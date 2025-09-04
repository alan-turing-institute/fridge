from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.core.v1 import Namespace

from enums import K8sEnvironment


class IngressArgs:
    def __init__(self, k8s_environment: K8sEnvironment, ingress_ns: Namespace):
        self.k8s_environment = k8s_environment
        self.ingress_ns = ingress_ns


class Ingress(ComponentResource):
    def __init__(self, name: str, args: IngressArgs, opts: ResourceOptions = None):
        super().__init__("fridge:k8s:Ingress", name, {}, opts)

        k8s_environment = args.k8s_environment

        match k8s_environment:
            case K8sEnvironment.AKS:
                # AKS specific configuration
                pass
            case K8sEnvironment.DAWN:
                # Dawn specific configuration
                pass
            case K8sEnvironment.K3S:
                # K3S specific configuration
                pass
