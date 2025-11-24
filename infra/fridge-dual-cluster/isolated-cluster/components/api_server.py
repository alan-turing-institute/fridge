import pulumi
from pulumi import ComponentResource, Output, ResourceOptions
from pulumi_kubernetes.apiextensions import CustomResource
from pulumi_kubernetes.apps.v1 import Deployment, DeploymentSpecArgs
from pulumi_kubernetes.core.v1 import (
    CapabilitiesArgs,
    ContainerArgs,
    ContainerPortArgs,
    EnvFromSourceArgs,
    Namespace,
    PodSpecArgs,
    PodTemplateSpecArgs,
    ProjectedVolumeSourceArgs,
    SeccompProfileArgs,
    Secret,
    SecretEnvSourceArgs,
    SecurityContextArgs,
    Service,
    ServiceAccount,
    ServiceAccountTokenProjectionArgs,
    ServicePortArgs,
    ServiceSpecArgs,
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

from enums import K8sEnvironment, PodSecurityStandard

API_SERVER_IMAGE = "ghcr.io/alan-turing-institute/fridge:main"


class ApiServerArgs:
    def __init__(
        self,
        argo_server_ns: str,
        argo_workflows_ns: str,
        config: pulumi.Config,
        minio_tenant_name: str,
        minio_url: Output[str],
        verify_tls: bool = True,
    ) -> None:
        self.argo_server_ns = argo_server_ns
        self.argo_workflows_ns = argo_workflows_ns
        self.config = config
        self.minio_tenant_name = minio_tenant_name
        self.minio_url = minio_url
        self.verify_tls = verify_tls


class ApiServer(ComponentResource):
    def __init__(
        self,
        name: str,
        args: ApiServerArgs,
        opts: ResourceOptions | None = None,
    ) -> None:
        super().__init__("fridge:ApiServer", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        api_server_ns = Namespace(
            "api-server-ns",
            metadata=ObjectMetaArgs(
                name="fridge-api",
                labels={} | PodSecurityStandard.RESTRICTED.value,
            ),
            opts=child_opts,
        )

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
                namespace=api_server_ns.metadata.name,
            ),
            opts=child_opts,
        )

        CustomResource(
            resource_name="minio-policy-readwrite",
            api_version="sts.min.io/v1alpha1",
            kind="PolicyBinding",
            metadata=ObjectMetaArgs(
                name="fridge-api-minio-readwrite",
                namespace=args.minio_tenant_name,
            ),
            spec={
                "application": {
                    # The namespace that contains the service account for the application
                    "namespace": fridge_api_sa.metadata.namespace,
                    # The service account to use for the application
                    "serviceaccount": fridge_api_sa.metadata.name,
                },
                "policies": ["readwrite"],
            },
            opts=ResourceOptions.merge(
                child_opts, ResourceOptions(depends_on=[fridge_api_sa])
            ),
        )

        fridge_api_config = Secret(
            "fridge-api-config",
            metadata=ObjectMetaArgs(
                name="fridge-api-config",
                namespace=api_server_ns.metadata.name,
            ),
            string_data={
                "ARGO_SERVER_NS": args.argo_server_ns,
                "FRIDGE_API_ADMIN": args.config.require_secret("fridge_api_admin"),
                "FRIDGE_API_PASSWORD": args.config.require_secret(
                    "fridge_api_password"
                ),
                "MINIO_URL": args.minio_url,
                "MINIO_TENANT_NAME": args.minio_tenant_name,
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
                    namespace=api_server_ns.metadata.name,
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
                namespace=api_server_ns.metadata.name,
            ),
            spec=DeploymentSpecArgs(
                replicas=1,
                selector=LabelSelectorArgs(match_labels={"app": "fridge-api-server"}),
                template=PodTemplateSpecArgs(
                    metadata=ObjectMetaArgs(labels={"app": "fridge-api-server"}),
                    spec=PodSpecArgs(
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
                                    ),
                                    VolumeMountArgs(
                                        name="minio-sa",
                                        mount_path="/minio",
                                        read_only=True,
                                    ),
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
                            VolumeArgs(
                                name="minio-sa",
                                projected=ProjectedVolumeSourceArgs(
                                    sources=[
                                        VolumeProjectionArgs(
                                            service_account_token=ServiceAccountTokenProjectionArgs(
                                                audience="sts.min.io",
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

        # Azure specific annotations for internal load balancer
        api_service_annotations = (
            {
                "service.beta.kubernetes.io/azure-load-balancer-internal": "true",
                "service.beta.kubernetes.io/azure-load-balancer-ipv4": args.config.require(
                    "fridge_api_ip"
                ),
            }
            if K8sEnvironment(args.config.get("k8s_env")) == K8sEnvironment.AKS
            else {}
        )

        self.api_service = Service(
            "fridge-api-service",
            metadata=ObjectMetaArgs(
                name="fridge-api",
                namespace=api_server_ns.metadata.name,
                labels={"app": "fridge-api-server"},
                annotations=api_service_annotations,
            ),
            spec=ServiceSpecArgs(
                type="LoadBalancer",
                selector=fridge_api_server.spec.template.metadata.labels,
                # load_balancer_source_ranges=[args.config.require("access_cluster_node_cidr")],
                ports=[
                    ServicePortArgs(
                        protocol="TCP",
                        port=443,
                        target_port=8000,
                    )
                ],
            ),
            opts=child_opts,
        )

        self.register_outputs(
            {
                "api_server_ns": api_server_ns,
                "argo_workflows_api_role": argo_workflows_api_role,
                "argo_workflows_api_rolebinding": argo_workflows_api_rolebinding,
                "fridge_api_config": fridge_api_config,
                "fridge_api_sa": fridge_api_sa,
                "fridge_api_server": fridge_api_server,
            }
        )
