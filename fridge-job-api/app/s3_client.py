import boto3
import os
import sys
import urllib3
from botocore.client import Config
from botocore.exceptions import ClientError
from fastapi import File, UploadFile, HTTPException
from io import BytesIO


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
            config=Config(signature_version="s3v4"),
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
        bucket_config = {}
        if region != "us-east-1":
            bucket_config["CreateBucketConfiguration"] = {"LocationConstraint": region}
        self.client.create_bucket(Bucket=name, **bucket_config)
        try:
            self.client.create_bucket(Bucket=name)

        except ClientError as e:
            self.handle_s3_error(e)

    def list_buckets(self):
        try:
            response = self.client.list_buckets()
            return [bucket["Name"] for bucket in response.get("Buckets", [])]
        except ClientError as e:
            self.handle_s3_error(e)

    async def put_object(self, bucket, file: UploadFile = File(...)):
        try:
            content = await file.read()
            result = self.client.put_object(
                bucket,
                file.filename,
                data=BytesIO(content),
                length=len(content),
                content_type=file.content_type,
            )
        except ClientError as error:
            self.handle_s3_error(error)
        except Exception as error:
            raise HTTPException(
                status_code=500, detail=f"Unable to upload object: {error}"
            )

        return {
            "status": 201,
            "response": getattr(result, "location", "None")
            or getattr(result, "_location", "None"),
            "version": getattr(result, "version_id", "None"),
        }
