from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.core.v1 import Namespace

from enums import K8sEnvironment


class CertManagerArgs:
    def __init__(self, k8s_environment: K8sEnvironment, cert_manager_ns: Namespace):
        self.k8s_environment = k8s_environment


class CertManager(ComponentResource):
    def __init__(self, name: str, args: CertManagerArgs, opts: ResourceOptions = None):
        super().__init__("fridge:k8s:CertManager", name, {}, opts)

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
