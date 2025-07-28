from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.apps.v1 import Deployment, DeploymentSpecArgs
from pulumi_kubernetes.core.v1 import Namespace, ServiceAccount
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs


class ApiServer(ComponentResource):
    def __init__(
        self,
        name: str,
        api_server_ns: str,
        opts: ResourceOptions,
    ) -> None:
        super().__init__("fridge:k8s:ApiServer", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        api_sa = ServiceAccount(
            "fridge-api-serviceaccount",
            metadata=ObjectMetaArgs(name="fridge-api-sa", namespace=api_server_ns),
            opts=child_opts,
        )

        api_server = Deployment(
            "fridge-api-server",
            metadata=ObjectMetaArgs(
                name="fridge-api-server",
                namespace=api_server_ns,
            ),
            spec=DeploymentSpecArgs(
                replicas=1,
                selector={"match_labels": {"app": "fridge-api-server"}},
                template={
                    "metadata": {"labels": {"app": "fridge-api-server"}},
                    "spec": {
                        "containers": [
                            {
                                "name": "fridge-api-server",
                                "image": "harbor.aks.fridge.develop.turingsafehaven.ac.uk/internal/fridge-api:latest",
                                "ports": [{"container_port": 8000}],
                                "volumeMounts": [
                                    {
                                        "name": "token-vol",
                                        "mountPath": "/service-account",
                                        "readOnly": True,
                                    }
                                ],
                            }
                        ],
                        "service_account_name": "fridge-api-sa",
                        "volumes": [
                            {
                                "name": "token-vol",
                                "projected": {
                                    "sources": [
                                        {
                                            "serviceAccountToken": {
                                                "audience": "api",
                                                "expirationSeconds": 3600,
                                                "path": "token",
                                            }
                                        }
                                    ]
                                },
                            }
                        ],
                    },
                },
            ),
            opts=child_opts,
        )
