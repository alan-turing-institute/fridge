from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.apps.v1 import Deployment, DeploymentSpecArgs
from pulumi_kubernetes.core.v1 import (
    CapabilitiesArgs,
    ContainerArgs,
    ContainerPortArgs,
    PodSpecArgs,
    PodTemplateSpecArgs,
    SeccompProfileArgs,
    SecurityContextArgs,
    ServiceAccount,
)
from pulumi_kubernetes.meta.v1 import LabelSelectorArgs, ObjectMetaArgs
from pulumi_kubernetes.rbac.v1 import (
    PolicyRuleArgs,
    Role,
    RoleBinding,
    RoleRefArgs,
    SubjectArgs,
)


class ApiRbac(ComponentResource):
    def __init__(
        self,
        name: str,
        api_server_ns: str,
        argo_workflows_ns: str,
        harbor_fqdn: str,
        opts=ResourceOptions,
    ) -> None:
        super().__init__("fridge:k8s:ApiRbac", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        # Define argo workflows service accounts and roles
        # See https://argo-workflows.readthedocs.io/en/latest/security/
        argo_workflows_api_role = Role(
            "argo-workflows-api-role",
            metadata=ObjectMetaArgs(
                name="argo-workflows-api-role",
                namespace=argo_workflows_ns,
            ),
            rules=[
                PolicyRuleArgs(
                    api_groups=["argoproj.io"],
                    resources=[
                        "workflowtemplates",
                    ],
                    verbs=[
                        "get",
                        "list",
                        "watch",
                        "update",
                    ],
                ),
                PolicyRuleArgs(
                    api_groups=["argoproj.io"],
                    resources=[
                        "workflows",
                    ],
                    verbs=[
                        "create",
                        "get",
                        "list",
                        "watch",
                        "update",
                    ],
                ),
            ],
            opts=child_opts,
        )

        fridge_api_sa = ServiceAccount(
            "fridge-api-sa",
            metadata=ObjectMetaArgs(
                name="fridge-api-sa",
                namespace=api_server_ns,
            ),
            opts=child_opts,
        )

        argo_workflows_api_role_binding = RoleBinding(
            "argo-workflows-api-role-binding",
            metadata=ObjectMetaArgs(
                name="argo-workflows-api-role-binding",
                namespace=argo_workflows_ns,
            ),
            role_ref=RoleRefArgs(
                api_group="rbac.authorization.k8s.io",
                kind="Role",
                name=argo_workflows_api_role.metadata.name,
            ),
            subjects=[
                SubjectArgs(
                    kind="ServiceAccount",
                    name=fridge_api_sa.metadata.name,
                    namespace=api_server_ns,
                )
            ],
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[argo_workflows_api_role, fridge_api_sa]),
            ),
        )

        api_server = Deployment(
            "fridge-api-server",
            metadata=ObjectMetaArgs(
                name="fridge-api-server",
                namespace=api_server_ns,
            ),
            spec=DeploymentSpecArgs(
                replicas=1,
                selector=LabelSelectorArgs(match_labels={"app": "fridge-api-server"}),
                template=PodTemplateSpecArgs(
                    metadata=ObjectMetaArgs(labels={"app": "fridge-api-server"}),
                    spec=PodSpecArgs(
                        automount_service_account_token=False,
                        containers=[
                            ContainerArgs(
                                name="fridge-api-server",
                                image="harbor.aks.fridge.develop.turingsafehaven.ac.uk/internal/fridge-api:latest",
                                ports=[ContainerPortArgs(container_port=8000)],
                                security_context=SecurityContextArgs(
                                    allow_privilege_escalation=False,
                                    capabilities=CapabilitiesArgs(
                                        drop=["ALL"],
                                    ),
                                    run_as_user=1001,
                                    run_as_group=3000,
                                    run_as_non_root=True,
                                    seccomp_profile=SeccompProfileArgs(
                                        type="RuntimeDefault"
                                    ),
                                ),
                                volume_mounts=[
                                    {
                                        "name": "token-vol",
                                        "mountPath": "/service-account",
                                        "readOnly": True,
                                    }
                                ],
                            )
                        ],
                        service_account_name=fridge_api_sa.metadata.name,
                        volumes=[
                            {
                                "name": "token-vol",
                                "projected": {
                                    "sources": [
                                        {
                                            "serviceAccountToken": {
                                                "expirationSeconds": 3600,
                                                "path": "token",
                                            }
                                        }
                                    ]
                                },
                            }
                        ],
                    ),
                ),
            ),
            opts=child_opts,
        )
