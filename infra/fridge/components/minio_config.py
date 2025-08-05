from string import Template
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


class MinioConfigArgs:
    def __init__(
        self, minio_tenant_ns: Namespace, minio_tenant: Chart, minio_credentials: dict
    ):
        self.minio_tenant_ns = minio_tenant_ns
        self.minio_tenant = minio_tenant
        self.minio_credentials = minio_credentials


class MinioConfigJob(ComponentResource):
    def __init__(self, name: str, args: MinioConfigArgs, opts=ResourceOptions) -> None:
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

        policies = {
            "read_only_ingress": """
            {
                "version": "2012-10-17",
                "statement": [
                    {
                        "Effect": "Allow",
                        "action": [
                            "s3:GetBucketLocation",
                            "s3:GetObject",
                            "s3:ListBucket"
                        ],
                        "resource": [
                            "arn:aws:s3:::ingress",
                            "arn:aws:s3:::ingress/*"
                        ]
                    }
                ]
            }
            """,
            "read_only_sensitive_ingress": """
            {
                "version": "2012-10-17",
                "statement": [
                    {
                        "Effect": "Allow",
                        "action": [
                            "s3:GetBucketLocation",
                            "s3:GetObject",
                            "s3:ListBucket"
                        ],
                        "resource": [
                            "arn:aws:s3:::sensitive-ingress",
                            "arn:aws:s3:::sensitive-ingress/*"
                        ]
                    }
                ]
            }
            """,
            "write_only_ready_for_review": """
            {
                "version": "2012-10-17",
                "statement": [
                    {
                        "Effect": "Allow",
                        "action": [
                            "s3:PutObject"
                        ],
                        "resource": [
                            "arn:aws:s3:::ready-for-review",
                            "arn:aws:s3:::ready-for-review/*"
                        ]
                    }
                ]
            }
            """,
            "read_only_ready_for_review": """
            {
                "version": "2012-10-17",
                "statement": [
                    {
                        "Effect": "Allow",
                        "action": [
                            "s3:GetBucketLocation",
                            "s3:GetObject",
                            "s3:ListBucket"
                        ],
                        "resource": [
                            "arn:aws:s3:::ready-for-review",
                            "arn:aws:s3:::ready-for-review/*"
                        ]
                    }
                ]
            }
            """,
            "write_only_ready_for_egress": """
            {
                "version": "2012-10-17",
                "statement": [
                    {
                        "Effect": "Allow",
                        "action": [
                            "s3:PutObject"
                        ],
                        "resource": [
                            "arn:aws:s3:::ready-for-egress",
                            "arn:aws:s3:::ready-for-egress/*"
                        ]
                    }
                ]
            }
            """,
            "argo-workflows-pod-policy": """
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "s3:PutObject"
                        ],
                        "Resource": [
                            "arn:aws:s3:::ready-for-egress",
                            "arn:aws:s3:::ready-for-egress/*"
                        ]
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "s3:GetBucketLocation",
                            "s3:GetObject",
                            "s3:ListBucket"
                        ],
                        "Resource": [
                            "arn:aws:s3:::ingress",
                            "arn:aws:s3:::ingress/*"
                        ]
                    }
                ]
            }
        """,
        }

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
                "read-only-ingress.json": policies["read_only_ingress"],
                "read-only-sensitive-ingress.json": policies[
                    "read_only_sensitive_ingress"
                ],
                "write-only-ready-for-review.json": policies[
                    "write_only_ready_for_review"
                ],
                "read-only-ready-for-review.json": policies[
                    "read_only_ready_for_review"
                ],
                "write-only-ready-for-egress.json": policies[
                    "write_only_ready_for_egress"
                ],
            },
            opts=child_opts,
        )

        # Create a Job to configure MinIO
        minio_config_job = Job(
            "minio-config-job",
            metadata=ObjectMetaArgs(
                name="minio-config-job",
                namespace=args.minio_tenant_ns.metadata.name,
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
