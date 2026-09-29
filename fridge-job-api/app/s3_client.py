import boto3
from botocore.client import Config
from botocore.exceptions import ClientError


class S3Client:
    def __init__(self, endpoint, access_key, secret_key, secure=True):
        scheme = "https" if secure else "http"
        self.client = boto3.client(
            "s3",
            endpoint_url=f"{scheme}://{endpoint}",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="us-east-1",
            config=Config(signature_version="s3v4"),
        )
