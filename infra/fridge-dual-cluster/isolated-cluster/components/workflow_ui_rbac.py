import pulumi
from pulumi import ComponentResource, Output, ResourceOptions
from pulumi_kubernetes.core.v1 import Secret, ServiceAccount
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs
from pulumi_kubernetes.rbac.v1 import (
    PolicyRuleArgs,
    Role,
    RoleBinding,
    RoleRefArgs,
    SubjectArgs,
)


class WorkflowUiRbacArgs:
    def __init__(
        self,
        argo_server_ns: str,
        argo_workflows_ns: str,
        config: pulumi.config.Config,
    ) -> None:
        self.argo_server_ns = argo_server_ns
        self.argo_workflows_ns = argo_workflows_ns
        self.config = config


class WorkflowUiRbac(ComponentResource):
    def __init__(
        self, name: str, args: WorkflowUiRbacArgs, opts: ResourceOptions = None
    ):
        super().__init__("fridge:components:WorkflowUIRbac", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        # Define argo workflows service accounts and roles
        # See https://argo-workflows.readthedocs.io/en/latest/security/
        # The admin service account gives users in the admin entra group
        # permission to run workflows in the Argo Workflows namespace
        argo_workflows_admin_role = Role(
            "argo-workflows-admin-role",
            metadata=ObjectMetaArgs(
                name="argo-workflows-admin-role",
                namespace=args.argo_workflows_ns,
            ),
            rules=[
                PolicyRuleArgs(
                    api_groups=[""],
                    resources=["events", "pods", "pods/log"],
                    verbs=["get", "list", "watch"],
                ),
                PolicyRuleArgs(
                    api_groups=["argoproj.io"],
                    resources=[
                        "cronworkflows",
                        "eventsources",
                        "workflows",
                        "workflows/finalizers",
                        "workflowtaskresults",
                        "workflowtemplates",
                        "clusterworkflowtemplates",
                    ],
                    verbs=[
                        "create",
                        "delete",
                        "deletecollection",
                        "get",
                        "list",
                        "patch",
                        "watch",
                        "update",
                    ],
                ),
            ],
            opts=child_opts,
        )

        argo_workflows_admin_sa = ServiceAccount(
            "argo-workflows-admin-sa",
            metadata=ObjectMetaArgs(
                name="argo-workflows-admin-sa",
                namespace=args.argo_workflows_ns,
                annotations={
                    "workflows.argoproj.io/rbac-rule": Output.concat(
                        "'",
                        args.config.require_secret("oidc_admin_group_id"),
                        "'",
                        " in groups",
                    ),
                    "workflows.argoproj.io/rbac-rule-precedence": "2",
                },
            ),
            opts=child_opts,
        )

        argo_workflows_admin_sa_token = Secret(
            "argo-workflows-admin-sa-token",
            metadata=ObjectMetaArgs(
                name="argo-workflows-admin-sa.service-account-token",
                namespace=args.argo_workflows_ns,
                annotations={
                    "kubernetes.io/service-account.name": argo_workflows_admin_sa.metadata.name,
                },
            ),
            type="kubernetes.io/service-account-token",
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[argo_workflows_admin_sa]),
            ),
        )

        argo_workflows_admin_role_binding = RoleBinding(
            "argo-workflows-admin-role-binding",
            metadata=ObjectMetaArgs(
                name="argo-workflows-admin-role-binding",
                namespace=args.argo_workflows_ns,
            ),
            role_ref=RoleRefArgs(
                api_group="rbac.authorization.k8s.io",
                kind="Role",
                name=argo_workflows_admin_role.metadata.name,
            ),
            subjects=[
                SubjectArgs(
                    kind="ServiceAccount",
                    name=argo_workflows_admin_sa.metadata.name,
                    namespace=args.argo_workflows_ns,
                )
            ],
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[argo_workflows_admin_role]),
            ),
        )

        # The admin service account above does not give permission to access the server workspace,
        # so the default service account below allows them to get sufficient access to use the UI
        # without being able to run workflows in the server namespace
        argo_workflows_default_sa = ServiceAccount(
            "argo-workflows-default-sa",
            metadata=ObjectMetaArgs(
                name="user-default-login",
                namespace=args.argo_server_ns,
                annotations={
                    "workflows.argoproj.io/rbac-rule": "true",
                    "workflows.argoproj.io/rbac-rule-precedence": "0",
                },
            ),
            opts=child_opts,
        )

        argo_workflows_default_sa_token = Secret(
            "argo-workflows-default-sa-token",
            metadata=ObjectMetaArgs(
                name="user-default-login.service-account-token",
                namespace=args.argo_server_ns,
                annotations={
                    "kubernetes.io/service-account.name": argo_workflows_default_sa.metadata.name,
                },
            ),
            type="kubernetes.io/service-account-token",
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[argo_workflows_default_sa]),
            ),
        )

        self.register_outputs(
            {
                "argo-workflows-admin-role": argo_workflows_admin_role,
                "argo-workflows-admin-role-binding": argo_workflows_admin_role_binding,
                "argo-workflows-admin-sa": argo_workflows_admin_sa,
                "argo-workflows-admin-sa-token": argo_workflows_admin_sa_token,
                "argo-workflows-default-sa": argo_workflows_default_sa,
                "argo-workflows-default-sa-token": argo_workflows_default_sa_token,
            }
        )
