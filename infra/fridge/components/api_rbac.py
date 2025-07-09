from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.core.v1 import (
    Secret,
    ServiceAccount,
)
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs
from pulumi_kubernetes.rbac.v1 import (
    PolicyRuleArgs,
    Role,
    RoleBinding,
    RoleRefArgs,
    SubjectArgs,
)


class ApiRbac(ComponentResource):
    def __init__(self, name: str, argo_workflows_ns: str, opts=ResourceOptions) -> None:
        super().__init__("fridge:k8s:ApiRbac", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        # Define argo workflows service accounts and roles
        # See https://argo-workflows.readthedocs.io/en/latest/security/
        # The admin service account gives users in the admin entra group
        # permission to run workflows in the Argo Workflows namespace
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
                        "workflows",
                        "workflowtemplates",
                        "workfloweventbindings",
                    ],
                    verbs=[
                        "get",
                        "list",
                        "watch",
                        "update",
                    ],
                ),
            ],
            opts=child_opts,
        )

        argo_workflows_api_sa = ServiceAccount(
            "argo-workflows-api-sa",
            metadata=ObjectMetaArgs(
                name="argo-workflows-api-sa",
                namespace=argo_workflows_ns,
            ),
            opts=child_opts,
        )

        argo_workflows_api_sa_token = Secret(
            "argo-workflows-api-sa-token",
            metadata=ObjectMetaArgs(
                name="argo-workflows-api-sa.service-account-token",
                namespace=argo_workflows_ns,
                annotations={
                    "kubernetes.io/service-account.name": argo_workflows_api_sa.metadata.name,
                },
            ),
            type="kubernetes.io/service-account-token",
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
                    name=argo_workflows_api_sa.metadata.name,
                    namespace=argo_workflows_ns,
                )
            ],
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(
                    depends_on=[argo_workflows_api_role, argo_workflows_api_sa]
                ),
            ),
        )

        self.register_outputs({"api-token": argo_workflows_api_sa_token})
