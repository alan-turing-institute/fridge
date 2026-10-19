import pulumi
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
    PodSpecArgs,
    PodTemplateSpecArgs,
    SecurityContextArgs,
    VolumeMountArgs,
    VolumeArgs,
)
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs

from enums import SoftwareVersion


class SeaweedConfigArgs:
    def __init__(
        self,
        config: pulumi.config.Config,
        seaweedfs: ComponentResource,
    ):
        self.config = config
        self.seaweedfs = seaweedfs


class SeaweedConfigJob(ComponentResource):
    def __init__(
        self, name: str, args: SeaweedConfigArgs, opts: ResourceOptions | None = None
    ) -> None:
        super().__init__("fridge:k8s:SeaweedConfigJob", name, {}, opts)
        child_opts = ResourceOptions.merge(opts, ResourceOptions(parent=self))

        setup_sh = """#!/bin/sh
            set -u

            MAX_RETRIES=15
            RETRY_INTERVAL=5

            echo "SeaweedFS bucket setup starting"
            echo "Endpoint: $S3_URL"
            echo "Buckets: ingress egress"

            for b in ingress egress; do
                echo "Creating bucket: $b"
                i=0
                while :; do
                    code=$(curl -s -o /tmp/response.txt -w '%{http_code}' -X PUT \\
                        --cacert /tmp/ca/ca.crt \\
                        --aws-sigv4 "aws:amz:us-east-1:s3" \\
                        --user "$S3_ACCESS_KEY:$S3_SECRET_KEY" \\
                        "$S3_URL/$b")
                    rc=$?
                    echo "[$b] Attempt $i/$MAX_RETRIES: curl exit=$rc http=$code"

                    case "$code" in
                        200) echo "[$b] Bucket created"; break;;
                        409) echo "[$b] Bucket already exists, nothing to do"; break;;
                    esac

                    [ -s /tmp/response.txt ] && echo "[$b] Response: $(cat /tmp/response.txt)"
                    if [ $i -ge $MAX_RETRIES ]; then
                        echo "[$b] Giving up after $MAX_RETRIES attempts"
                        exit 1
                    fi
                    echo "[$b] Retrying in $RETRY_INTERVAL seconds"
                    sleep $RETRY_INTERVAL
                done
            done

            echo "SeaweedFS bucket setup complete"
            """

        # Create a ConfigMap for SeaweedFS configuration
        seaweed_config_map = ConfigMap(
            "seaweedfs-configuration",
            metadata=ObjectMetaArgs(
                name="seaweedfs-configuration",
                namespace=args.seaweedfs.seaweedfs_ns.metadata.name,
            ),
            data={
                "setup.sh": setup_sh,
            },
            opts=child_opts,
        )

        # Create a Job to configure SeaweedFS
        seaweed_config_job = Job(
            "seaweedfs-config-job",
            metadata=ObjectMetaArgs(
                name="seaweedfs-config-job",
                namespace=args.seaweedfs.seaweedfs_ns.metadata.name,
                labels={"app": "seaweedfs-config-job"},
            ),
            spec=JobSpecArgs(
                backoff_limit=2,
                template=PodTemplateSpecArgs(
                    metadata=ObjectMetaArgs(
                        # This ensures the generated Pods actually get the label
                        labels={"app": "seaweedfs-config-job"},
                    ),
                    spec=PodSpecArgs(
                        containers=[
                            ContainerArgs(
                                name="seaweedfs-config-job",
                                image=f"curlimages/curl:{SoftwareVersion.CURL.value}",
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
                                    EnvVarArgs(
                                        name="S3_URL",
                                        value=Output.concat(
                                            "https://",
                                            args.seaweedfs.seaweedfs_s3_endpoint,
                                        ),
                                    ),
                                    EnvVarArgs(
                                        name="S3_ACCESS_KEY",
                                        value=args.config.require_secret(
                                            "s3_access_key"
                                        ),
                                    ),
                                    EnvVarArgs(
                                        name="S3_SECRET_KEY",
                                        value=args.config.require_secret(
                                            "s3_secret_key"
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
                                        name="seaweedfs-config-volume",
                                        mount_path="/tmp/scripts/",
                                    ),
                                    VolumeMountArgs(
                                        name="seaweedfs-tls-ca",
                                        mount_path="/tmp/ca/",
                                        read_only=True,
                                    ),
                                ],
                            )
                        ],
                        volumes=[
                            VolumeArgs(
                                name="seaweedfs-config-volume",
                                config_map=ConfigMapVolumeSourceArgs(
                                    name=seaweed_config_map.metadata.name,
                                    default_mode=0o777,
                                ),
                            ),
                            VolumeArgs(
                                name="seaweedfs-tls-ca",
                                secret={
                                    "secretName": "seaweedfs-tls",
                                    "items": [{"key": "ca.crt", "path": "ca.crt"}],
                                },
                            ),
                        ],
                        restart_policy="Never",
                    ),
                ),
            ),
            opts=ResourceOptions.merge(
                child_opts,
                ResourceOptions(depends_on=[args.seaweedfs]),
            ),
        )
