import os
from pulumi import ComponentResource, ResourceOptions
from pulumi_kubernetes.batch.v1 import (
    Job,
    JobSpecArgs,
)
from pulumi_kubernetes.core.v1 import (
    ConfigMap,
    ConfigMapVolumeSourceArgs,
    ContainerArgs,
    EnvVarArgs,
    Namespace,
    PodSpecArgs,
    PodTemplateSpecArgs,
    SecurityContextArgs,
    VolumeMountArgs,
    VolumeArgs,
)
from pulumi_kubernetes.helm.v4 import Chart
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs


def load_policy(name: str) -> str:
    """
    Load a policy from the policies directory.
    """
    with open(
        os.path.join(os.path.dirname(__file__), "minio_policies", name), "r"
    ) as f:
        return f.read()


class MinioConfigArgs:
    def __init__(
        self, minio_tenant_ns: Namespace, minio_tenant: Chart, minio_credentials: dict
    ):
        self.minio_tenant_ns = minio_tenant_ns
        self.minio_tenant = minio_tenant
        self.minio_credentials = minio_credentials


class MinioConfigJob(ComponentResource):
    def __init__(
        self, name: str, args: MinioConfigArgs, opts: ResourceOptions | None = None
    ) -> None:
        super().__init__("fridge:k8s:MinioConfigJob", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        minio_setup_sh = """
            echo "Creating default S3 policies"
            for policy in /tmp/scripts/*.json; do
                echo "Creating policy $policy"
                mc --insecure admin policy create $1 $(basename "$policy" .json) "$policy"
                echo "Policy $(basename "$policy" .json) created"
            done
        """

        # Create a ConfigMap for MinIO configuration
        minio_config_map = ConfigMap(
            "minio-configuration",
            metadata=ObjectMetaArgs(
                name="minio-configuration",
                namespace=args.minio_tenant_ns.metadata.name,
            ),
            data={
                "MINIO_ALIAS": "argoartifacts",
                "MINIO_URL": "http://minio.argo-artifacts.svc.cluster.local:80",
                "MINIO_NAMESPACE": args.minio_tenant_ns.metadata.name,
                "setup.sh": minio_setup_sh,
                "read-only-ingress.json": load_policy("read-only-ingress.json"),
                "read-only-sensitive-ingress.json": load_policy(
                    "read-only-sensitive-ingress.json"
                ),
                "write-only-ready-for-review.json": load_policy(
                    "write-only-ready-for-review.json"
                ),
                "read-only-ready-for-review.json": load_policy(
                    "read-only-ready-for-review.json"
                ),
                "write-only-ready-for-egress.json": load_policy(
                    "write-only-ready-for-egress.json"
                ),
                "argo-workflows-pod-policy.json": load_policy(
                    "argo-workflows-pod-policy.json"
                ),
            },
            opts=child_opts,
        )

        # Create a Job to configure MinIO
        Job(
            "minio-config-job",
            metadata=ObjectMetaArgs(
                name="minio-config-job",
                namespace=args.minio_tenant_ns.metadata.name,
                labels={"app": "minio-config-job"},
            ),
            spec=JobSpecArgs(
                backoff_limit=1,
                template=PodTemplateSpecArgs(
                    spec=PodSpecArgs(
                        containers=[
                            ContainerArgs(
                                name="minio-config-job",
                                image="minio/mc:latest",
                                command=[
                                    "/bin/sh",
                                    "-c",
                                ],
                                args=[
                                    "mc --insecure alias set argoartifacts http://minio.argo-artifacts.svc.cluster.local:80 $(MINIO_ROOT_USER) $(MINIO_ROOT_PASSWORD) &&"
                                    "/tmp/scripts/setup.sh argoartifacts;",
                                ],
                                resources={
                                    "requests": {
                                        "cpu": "100m",
                                        "memory": "128Mi",
                                    },
                                    "limits": {
                                        "cpu": "100m",
                                        "memory": "128Mi",
                                    },
                                },
                                env=[
                                    EnvVarArgs(name="MC_CONFIG_DIR", value="/tmp/.mc"),
                                    EnvVarArgs(
                                        name="MINIO_ROOT_USER",
                                        value=args.minio_credentials.get(
                                            "minio_root_user", ""
                                        ),
                                    ),
                                    EnvVarArgs(
                                        name="MINIO_ROOT_PASSWORD",
                                        value=args.minio_credentials.get(
                                            "minio_root_password", ""
                                        ),
                                    ),
                                ],
                                security_context=SecurityContextArgs(
                                    allow_privilege_escalation=False,
                                    capabilities={"drop": ["ALL"]},
                                    run_as_group=1000,
                                    run_as_non_root=True,
                                    run_as_user=1000,
                                    seccomp_profile={"type": "RuntimeDefault"},
                                ),
                                volume_mounts=[
                                    VolumeMountArgs(
                                        name="minio-config-volume",
                                        mount_path="/tmp/scripts/",
                                    )
                                ],
                            )
                        ],
                        volumes=[
                            VolumeArgs(
                                name="minio-config-volume",
                                config_map=ConfigMapVolumeSourceArgs(
                                    name=minio_config_map.metadata.name,
                                    default_mode=0o777,
                                ),
                            )
                        ],
                        restart_policy="Never",
                    ),
                ),
            ),
            opts=child_opts,
        )
