import boto3
import os
import sys
from botocore.client import Config
from botocore.exceptions import ClientError
from boto3.s3.transfer import TransferConfig
from fastapi import UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from io import BytesIO
from starlette.concurrency import run_in_threadpool


_TRANSFER_CONFIG = TransferConfig(
    multipart_threshold=8 * 1024 * 1024,  # start multipart above 8MB
    multipart_chunksize=64 * 1024 * 1024,  # 64MB parts keeps part count sane for 100GB+
    max_concurrency=10,
    use_threads=True,
)


class S3Client:

    S3_CA_CRT = os.getenv("S3_CA_BUNDLE") or "/etc/ssl/certs/ca-certificates.crt"

    def __init__(self, endpoint, access_key, secret_key, secure=True):
        scheme = "https" if secure else "http"

        # Exit if s3 client keys are not available
        if access_key is None or secret_key is None:
            print("Failed to initialise S3 client")
            sys.exit(1)

        self.client = boto3.client(
            "s3",
            endpoint_url=f"{scheme}://{endpoint}",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="us-east-1",
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
            verify=self.S3_CA_CRT if os.path.exists(self.S3_CA_CRT) else True,
        )
        print("Successfully configured S3 client")

    def handle_s3_error(self, error: ClientError):
        code = error.response["Error"]["Code"]
        status = {"NoSuchBucket": 404, "NoSuchKey": 404, "AccessDenied": 403}.get(
            code, 500
        )
        raise HTTPException(
            status_code=status, detail=error.response["Error"]["Message"]
        )

    def create_bucket(self, name, region="us-east-1"):
        """
        Creates a new S3 bucket.

        :param name: Name of the bucket to create
        :param region: This is a required parameter, but is a placeholder.
        """
        bucket_config = {}
        if region != "us-east-1":
            bucket_config["CreateBucketConfiguration"] = {"LocationConstraint": region}
        try:
            self.client.create_bucket(Bucket=name, **bucket_config)
        except ClientError as e:
            self.handle_s3_error(e)

    def list_buckets(self):
        try:
            response = self.client.list_buckets(
                MaxBuckets=200,
            )
            return [bucket["Name"] for bucket in response.get("Buckets", [])]
        except ClientError as e:
            self.handle_s3_error(e)

    async def put_object(self, bucket, file: UploadFile):
        """
        Streams a file to the specified S3 bucket via multipart upload, without buffering in memory

        :param file: File to upload
        :param bucket: S3 bucket to upload to
        """
        try:
            await run_in_threadpool(
                self.client.upload_fileobj,
                Fileobj=file.file,
                Bucket=bucket,
                Key=file.filename,
                ExtraArgs={"ContentType": file.content_type},
                Config=_TRANSFER_CONFIG,
            )
        except ClientError as error:
            self.handle_s3_error(error)
        except Exception as error:
            raise HTTPException(
                status_code=500, detail=f"Unable to upload object: {error}"
            )

        try:
            head = self.client.head_object(Bucket=bucket, Key=file.filename)
        except ClientError:
            head = {}

        return {
            "status": 201,
            "response": file.filename,
            "version": head.get("VersionId", "None"),
        }

    def get_object(self, bucket, file_name, target_file=None, version=None):
        """
        Retrieves an object from the specified S3 bucket.

        :param bucket: S3 bucket to retrieve the object from
        :param file_name: Name of the object to retrieve
        :param target_file: Optional file to save the retrieved object to
        :param version: Optional version of the object to retrieve
        """
        try:
            get_object_params = {"Bucket": bucket, "Key": file_name}
            if version:
                get_object_params["VersionId"] = version

            response = self.client.get_object(**get_object_params)
            if not target_file:
                target_file = file_name
            return StreamingResponse(
                response["Body"],
                media_type=response.get("ContentType", "application/octet-stream"),
                headers={
                    "Content-Disposition": f'attachment; filename="{target_file}"'
                },
            )
        except ClientError as error:
            self.handle_s3_error(error)

    def list_objects(self, bucket, prefix=None, recursive=False):
        """
        Lists objects in the specified S3 bucket.

        :param bucket: S3 bucket to list objects in
        :param prefix: Optional prefix to filter objects by
        :param recursive: Optional flag to list objects recursively
        :return: List of objects in the specified S3 bucket
        """
        try:
            list_objects_params = {"Bucket": bucket}
            if prefix:
                list_objects_params["Prefix"] = prefix

            response = self.client.list_objects_v2(**list_objects_params)
            objects = response.get("Contents", [])
            if not recursive:
                # Filter out objects that are not in the top-level directory
                objects = [
                    obj
                    for obj in objects
                    if "/" not in (obj["Key"][len(prefix) :] if prefix else obj["Key"])
                ]
            return [obj["Key"] for obj in objects]
        except ClientError as error:
            self.handle_s3_error(error)

    def check_object_exists(self, bucket, file_name, version=None):
        """
        Checks if an object exists in the specified S3 bucket.

        :param bucket: S3 bucket to check the object in
        :param file_name: Name of the object to check
        :param version: Optional version of the object to check
        :return: True if the object exists, False otherwise
        """
        try:
            head_params = {"Bucket": bucket, "Key": file_name}
            if version:
                head_params["VersionId"] = version

            self.client.head_object(**head_params)
            return True
        except ClientError as error:
            if error.response["Error"]["Code"] == "NoSuchKey":
                return False
            self.handle_s3_error(error)
            return False

    def delete_object(self, bucket, file_name, version=None):
        """
        Deletes an object from the specified S3 bucket.

        :param bucket: S3 bucket to delete the object from
        :param file_name: Name of the object to delete
        :param version: Optional version of the object to delete
        """
        try:
            delete_object_params = {"Bucket": bucket, "Key": file_name}
            if version:
                delete_object_params["VersionId"] = version

            self.client.delete_object(**delete_object_params)
            return {
                "status": 200,
                "response": f"Object {file_name} deleted from {bucket}",
            }
        except ClientError as error:
            self.handle_s3_error(error)
