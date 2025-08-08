from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.apps.v1 import Deployment, DeploymentSpecArgs
from pulumi_kubernetes.core.v1 import (
    CapabilitiesArgs,
    ContainerArgs,
    ContainerPortArgs,
    EnvFromSourceArgs,
    PodSpecArgs,
    PodTemplateSpecArgs,
    ProjectedVolumeSourceArgs,
    SeccompProfileArgs,
    Secret,
    SecretEnvSourceArgs,
    SecurityContextArgs,
    ServiceAccount,
    ServiceAccountTokenProjectionArgs,
    VolumeArgs,
    VolumeMountArgs,
    VolumeProjectionArgs,
)
from pulumi_kubernetes.meta.v1 import LabelSelectorArgs, ObjectMetaArgs
from pulumi_kubernetes.rbac.v1 import (
    PolicyRuleArgs,
    Role,
    RoleBinding,
    RoleRefArgs,
    SubjectArgs,
)

API_SERVER_IMAGE = "ghcr.io/alan-turing-institute/fridge:main"


class ApiServerArgs:
    def __init__(
        self,
        api_server_ns: str,
        argo_workflows_ns: str,
        fridge_api_admin: str,
        fridge_api_password: str,
        verify_tls: bool = True,
    ) -> None:
        self.api_server_ns = api_server_ns
        self.argo_workflows_ns = argo_workflows_ns
        self.fridge_api_admin = fridge_api_admin
        self.fridge_api_password = fridge_api_password
        self.verify_tls = verify_tls


class ApiServer(ComponentResource):
    def __init__(
        self,
        name: str,
        args: ApiServerArgs,
        opts=ResourceOptions,
    ) -> None:
        super().__init__("fridge:ApiServer", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        # Define argo workflows service accounts and roles
        # See https://argo-workflows.readthedocs.io/en/latest/security/
        argo_workflows_api_role = Role(
            "argo-workflows-api-role",
            metadata=ObjectMetaArgs(
                name="argo-workflows-api-role",
                namespace=args.argo_workflows_ns,
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
                namespace=args.api_server_ns,
            ),
            opts=child_opts,
        )

        fridge_api_config = Secret(
            "fridge-api-config",
            metadata=ObjectMetaArgs(
                name="fridge-api-config",
                namespace=args.api_server_ns,
            ),
            string_data={
                "FRIDGE_API_ADMIN": args.fridge_api_admin,
                "FRIDGE_API_PASSWORD": args.fridge_api_password,
                "VERIFY_TLS": str(args.verify_tls),
            },
            opts=child_opts,
        )

        argo_workflows_api_rolebinding = RoleBinding(
            "argo-workflows-api-role-binding",
            metadata=ObjectMetaArgs(
                name="argo-workflows-api-role-binding",
                namespace=args.argo_workflows_ns,
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
                    namespace=args.api_server_ns,
                )
            ],
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[argo_workflows_api_role, fridge_api_sa]),
            ),
        )

        fridge_api_server = Deployment(
            "fridge-api-server",
            metadata=ObjectMetaArgs(
                name="fridge-api-server",
                namespace=args.api_server_ns,
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
                                env_from=[
                                    EnvFromSourceArgs(
                                        secret_ref=SecretEnvSourceArgs(
                                            name=fridge_api_config.metadata.name
                                        )
                                    )
                                ],
                                image=API_SERVER_IMAGE,
                                image_pull_policy="Always",
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
                                    VolumeMountArgs(
                                        name="token-vol",
                                        mount_path="/service-account",
                                        read_only=True,
                                    )
                                ],
                            )
                        ],
                        service_account_name=fridge_api_sa.metadata.name,
                        volumes=[
                            VolumeArgs(
                                name="token-vol",
                                projected=ProjectedVolumeSourceArgs(
                                    sources=[
                                        VolumeProjectionArgs(
                                            service_account_token=ServiceAccountTokenProjectionArgs(
                                                expiration_seconds=3600,
                                                path="token",
                                            )
                                        )
                                    ]
                                ),
                            ),
                        ],
                    ),
                ),
            ),
            opts=child_opts,
        )

        self.register_outputs(
            {
                "argo_workflows_api_role": argo_workflows_api_role,
                "argo_workflows_api_rolebinding": argo_workflows_api_rolebinding,
                "fridge_api_config": fridge_api_config,
                "fridge_api_sa": fridge_api_sa,
                "fridge_api_server": fridge_api_server,
            }
        )
