import pulumi
from pulumi import ComponentResource, FileAsset, ResourceOptions
from pulumi_kubernetes.core.v1 import Namespace, Secret, ServiceAccount
from pulumi_kubernetes.helm.v4 import Chart, RepositoryOptsArgs
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs
from pulumi_kubernetes.rbac.v1 import (
    Role,
    RoleBinding,
    PolicyRuleArgs,
    RoleRefArgs,
    SubjectArgs,
)

from enums import PodSecurityStandard, TlsEnvironment


class WorkflowServerArgs:
    def __init__(
        self,
        config: pulumi.config.Config,
        tls_environment: TlsEnvironment,
    ):
        self.config = config
        self.tls_environment = tls_environment


class WorkflowServer(ComponentResource):
    def __init__(
        self, name: str, args: WorkflowServerArgs, opts: ResourceOptions | None = None
    ):
        super().__init__("fridge:WorkflowServer", name, None, opts=opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        argo_server_ns = Namespace(
            "argo-server-ns",
            metadata=ObjectMetaArgs(
                name="argo-server",
                labels={} | PodSecurityStandard.RESTRICTED.value,
            ),
            opts=child_opts,
        )

        argo_workflows_ns = Namespace(
            "argo-workflows-ns",
            metadata=ObjectMetaArgs(
                name="argo-workflows",
                labels={} | PodSecurityStandard.RESTRICTED.value,
            ),
            opts=child_opts,
        )

        argo_minio_secret = Secret(
            "argo-minio-secret",
            metadata=ObjectMetaArgs(
                name="argo-artifacts-minio",
                namespace=argo_workflows_ns.metadata.name,
            ),
            type="Opaque",
            string_data={
                "accesskey": args.config.require_secret("minio_root_user"),
                "secretkey": args.config.require_secret("minio_root_password"),
            },
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[argo_server_ns]),
            ),
        )

        argo_depends_on = [
            argo_minio_secret,
            argo_server_ns,
            argo_workflows_ns,
        ]

        argo_workflows = Chart(
            "argo-workflows",
            namespace=argo_server_ns.metadata.name,
            chart="argo-workflows",
            version="0.45.12",
            repository_opts=RepositoryOptsArgs(
                repo="https://argoproj.github.io/argo-helm",
            ),
            value_yaml_files=[
                FileAsset("./k8s/argo_workflows/values.yaml"),
            ],
            values={
                "controller": {
                    "extraArgs": [
                        "--namespaced",
                        "--managed-namespace",
                        argo_workflows_ns.metadata.name,
                    ],
                    "workflowNamespaces": [argo_workflows_ns.metadata.name],
                },
                "server": {
                    "authModes": ["server", "client"],
                    "extraArgs": [
                        "--namespaced",
                        "--managed-namespace",
                        argo_workflows_ns.metadata.name,
                    ],
                },
                "singleNamespace": True,
            },
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(
                    depends_on=argo_depends_on,
                ),
            ),
        )

        # The Argo Workflows helm chart does not handle roles/rolebindings for a managed-namespace setup
        # correctly, so we need to create these manually
        # It skips many service accounts and roles if `singleNamespace` is True,
        # but that flag is required to prevent it from setting up ClusterRoles.
        # ClusterRoles would allow the workflow controller to run workloads in any namespace

        self.workflow_role = Role(
            "argo-workflow-controller-role",
            metadata=ObjectMetaArgs(
                name="argo-workflow-controller-role",
                namespace=argo_workflows_ns.metadata.name,
            ),
            rules=[
                PolicyRuleArgs(
                    api_groups=[""],
                    resources=["pods", "pods/exec"],
                    verbs=[
                        "create",
                        "get",
                        "list",
                        "watch",
                        "update",
                        "patch",
                        "delete",
                    ],
                ),
                PolicyRuleArgs(
                    api_groups=[""],
                    resources=["configmaps"],
                    verbs=["get", "watch", "list"],
                ),
                PolicyRuleArgs(
                    api_groups=[""],
                    resources=[
                        "persistentvolumeclaims",
                        "persistentvolumeclaims/finalizers",
                    ],
                    verbs=["create", "update", "delete", "get"],
                ),
                PolicyRuleArgs(
                    api_groups=["argoproj.io"],
                    resources=[
                        "workflows",
                        "workflows/finalizers",
                        "workflowtasksets",
                        "workflowtasksets/finalizers",
                        "workflowartifactgctasks",
                    ],
                    verbs=[
                        "get",
                        "list",
                        "watch",
                        "update",
                        "patch",
                        "delete",
                        "create",
                    ],
                ),
                PolicyRuleArgs(
                    api_groups=["argoproj.io"],
                    resources=[
                        "workflowtemplates",
                        "cronworkflows",
                        "cronworkflows/finalizers",
                    ],
                    verbs=["get", "list", "watch"],
                ),
                PolicyRuleArgs(
                    api_groups=["argoproj.io"],
                    resources=["workflowtaskresults"],
                    verbs=["list", "watch", "deletecollection"],
                ),
                PolicyRuleArgs(
                    api_groups=[""],
                    resources=["serviceaccounts"],
                    verbs=["get", "list"],
                ),
                PolicyRuleArgs(
                    api_groups=["policy"],
                    resources=["poddisruptionbudgets"],
                    verbs=["create", "get", "delete"],
                ),
            ],
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[argo_workflows_ns]),
            ),
        )

        self.workflow_role_binding = RoleBinding(
            "argo-workflow-controller-role-binding",
            metadata=ObjectMetaArgs(
                name="argo-workflow-controller-role-binding",
                namespace=argo_workflows_ns.metadata.name,
            ),
            role_ref=RoleRefArgs(
                api_group="rbac.authorization.k8s.io",
                kind="Role",
                name=self.workflow_role.metadata.name,
            ),
            subjects=[
                SubjectArgs(
                    kind="ServiceAccount",
                    # This is the SA created by the Argo Helm chart
                    name="argo-workflows-workflow-controller",
                    namespace=argo_server_ns.metadata.name,
                )
            ],
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[self.workflow_role, argo_workflows]),
            ),
        )

        self.argo_server_role = Role(
            "argo-server-role",
            metadata=ObjectMetaArgs(
                name="argo-server-role",
                namespace=argo_workflows_ns.metadata.name,
            ),
            rules=[
                PolicyRuleArgs(
                    api_groups=["argoproj.io"],
                    resources=[
                        "workflows",
                        "workflows/finalizers",
                        "workflowtemplates",
                        "workflowtemplates/finalizers",
                        "cronworkflows",
                        "cronworkflows/finalizers",
                        "clusterworkflowtemplates",
                        "clusterworkflowtemplates/finalizers",
                    ],
                    verbs=[
                        "create",
                        "get",
                        "list",
                        "watch",
                        "update",
                        "patch",
                        "delete",
                    ],
                ),
                PolicyRuleArgs(
                    api_groups=["argoproj.io"],
                    resources=["workfloweventbindings"],
                    verbs=["list"],
                ),
                PolicyRuleArgs(
                    api_groups=[""],
                    resources=["pods", "pods/exec", "pods/log"],
                    verbs=["get", "list", "watch", "delete"],
                ),
                PolicyRuleArgs(
                    api_groups=[""],
                    resources=["events"],
                    verbs=["watch", "get", "list"],
                ),
                PolicyRuleArgs(
                    api_groups=[""],
                    resources=["serviceaccounts"],
                    verbs=["get", "list"],
                ),
            ],
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[argo_workflows_ns]),
            ),
        )

        self.argo_server_role_binding = RoleBinding(
            "argo-server-role-binding",
            metadata=ObjectMetaArgs(
                name="argo-server-role-binding",
                namespace=argo_workflows_ns.metadata.name,
            ),
            role_ref=RoleRefArgs(
                api_group="rbac.authorization.k8s.io",
                kind="Role",
                name=self.argo_server_role.metadata.name,
            ),
            subjects=[
                SubjectArgs(
                    kind="ServiceAccount",
                    # SA created by the Argo Helm chart for the server
                    name="argo-workflows-server",
                    namespace=argo_server_ns.metadata.name,
                )
            ],
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[self.argo_server_role, argo_workflows]),
            ),
        )

        self.executor_sa = ServiceAccount(
            "argo-workflow-executor-sa",
            metadata=ObjectMetaArgs(
                name="argo-workflow",
                namespace=argo_workflows_ns.metadata.name,
            ),
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[argo_workflows_ns]),
            ),
        )

        self.executor_role = Role(
            "argo-workflow-executor-role",
            metadata=ObjectMetaArgs(
                name="executor",
                namespace=argo_workflows_ns.metadata.name,
            ),
            rules=[
                PolicyRuleArgs(
                    api_groups=["argoproj.io"],
                    resources=["workflowtaskresults"],
                    verbs=["create", "patch"],
                ),
            ],
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[argo_workflows_ns]),
            ),
        )

        self.executor_role_binding = RoleBinding(
            "argo-workflow-executor-role-binding",
            metadata=ObjectMetaArgs(
                name="argo-workflow-executor-role-binding",
                namespace=argo_workflows_ns.metadata.name,
            ),
            role_ref=RoleRefArgs(
                api_group="rbac.authorization.k8s.io",
                kind="Role",
                name=self.executor_role.metadata.name,
            ),
            subjects=[
                SubjectArgs(
                    kind="ServiceAccount",
                    name=self.executor_sa.metadata.name,
                    namespace=argo_workflows_ns.metadata.name,
                )
            ],
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[self.executor_role, self.executor_sa]),
            ),
        )

        self.argo_server_ns = argo_server_ns.metadata.name
        self.argo_workflows_ns = argo_workflows_ns.metadata.name
        self.register_outputs(
            {
                "argo_workflows": argo_workflows,
                "argo_minio_secret": argo_minio_secret,
                "argo_server_ns": argo_server_ns,
                "argo_workflows_ns": argo_workflows_ns,
            }
        )
