from pulumi import ComponentResource, Output, ResourceOptions
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


class MinioConfigArgs:
    def __init__(
        self,
        minio_tenant_ns: Namespace,
        minio_tenant: Chart,
        minio_credentials: dict,
        minio_cluster_url: Output[str],
    ):
        self.minio_cluster_url = minio_cluster_url
        self.minio_credentials = minio_credentials
        self.minio_tenant_ns = minio_tenant_ns
        self.minio_tenant = minio_tenant


class MinioConfigJob(ComponentResource):
    def __init__(
        self, name: str, args: MinioConfigArgs, opts: ResourceOptions | None = None
    ) -> None:
        super().__init__("fridge:k8s:MinioConfigJob", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        minio_setup_sh = """
            #!/bin/sh
            mc --insecure alias set "$MINIO_ALIAS" "$MINIO_URL" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
            echo "Configuring ingress and egress buckets with anonymous S3 policies"
            mc anonymous set upload "$MINIO_ALIAS/egress"
            mc anonymous set download "$MINIO_ALIAS/ingress"
        """

        # Create a ConfigMap for MinIO configuration
        minio_config_map = ConfigMap(
            "minio-configuration",
            metadata=ObjectMetaArgs(
                name="minio-configuration",
                namespace=args.minio_tenant_ns.metadata.name,
            ),
            data={
                "setup.sh": minio_setup_sh,
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
                                    "/tmp/scripts/setup.sh",
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
                                        name="MINIO_ALIAS",
                                        value="argoartifacts",
                                    ),
                                    EnvVarArgs(
                                        name="MINIO_URL",
                                        value=Output.concat(
                                            "http://", args.minio_cluster_url, ":80"
                                        ),
                                    ),
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
