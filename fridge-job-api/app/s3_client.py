import boto3
import os
from boto3.s3.transfer import TransferConfig
from botocore.client import Config
from botocore.exceptions import ClientError
from contextlib import contextmanager
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from starlette.requests import ClientDisconnect


MiB = 1024 * 1024
GiB = 1024 * MiB
TiB = 1024 * GiB
# The largest object that can be uploaded
MAX_OBJECT_SIZE = 1 * TiB
# S3 allows at most 10,000 parts in a multipart upload
MAX_PART_COUNT = 10_000
# Smallest part size. Small enough that mid-sized files are still sent to S3 as several
# parts in parallel
STREAM_PART_SIZE = 16 * MiB
# Parts sent to S3 in parallel, and so held in memory, per upload
STREAM_CONCURRENCY = 4
# Total upload data the API holds in memory at once, across all requests
UPLOAD_MEMORY_BUDGET = 1 * GiB


def stream_part_size(size: int) -> int:
    """
    The part size to use for an object of `size` bytes: at least STREAM_PART_SIZE, and large
    enough, in whole MiB, for the object to fit in MAX_PART_COUNT parts (105MiB for 1TiB).
    """
    needed = -(-size // MAX_PART_COUNT)
    return max(STREAM_PART_SIZE, -(-needed // MiB) * MiB)


def stream_memory(size: int) -> int:
    """The most memory an upload of `size` bytes uses: the parts being sent, and the next."""
    return min(size, stream_part_size(size) * (STREAM_CONCURRENCY + 1))


def check_object_size(size: int) -> None:
    if size > MAX_OBJECT_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Files larger than {MAX_OBJECT_SIZE // GiB}GiB are not supported.",
        )


class MemoryBudget:
    """
    Limits the upload data held in memory across all requests, so that concurrent uploads
    cannot exhaust the pod's memory. A request that would go over the budget is refused
    straight away with a 503, rather than queued, as a queued upload would hold its
    connection open with nothing happening until the proxy timed it out.

    Only use from the event loop, not from a thread pool, as the count is not locked.
    """

    def __init__(self, limit: int):
        self.limit = limit
        self.used = 0

    @contextmanager
    def reserve(self, size: int):
        if self.used + size > self.limit:
            raise HTTPException(
                status_code=503,
                detail="The API is busy with other uploads. Try again shortly.",
                headers={"Retry-After": "10"},
            )
        self.used += size
        try:
            yield
        finally:
            self.used -= size


upload_memory = MemoryBudget(UPLOAD_MEMORY_BUDGET)


class S3Client:

    S3_CA_CRT = os.getenv("S3_CA_BUNDLE") or "/etc/ssl/certs/ca-certificates.crt"

    def __init__(self, endpoint, access_key, secret_key, secure=True):
        scheme = "https" if secure else "http"

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

    def handle_s3_error(self, error: ClientError):
        code = error.response["Error"]["Code"]
        status = {
            "NoSuchBucket": 404,
            "NoSuchKey": 404,
            "NoSuchUpload": 404,
            "404": 404,
            "EntityTooSmall": 400,
            "InvalidPart": 400,
            "InvalidPartOrder": 400,
            "403": 403,
            "AccessDenied": 403,
            "InvalidAccessKeyId": 401,
            "SignatureDoesNotMatch": 401,
        }.get(code, 500)
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

    def put_object(self, bucket, key, content_type, fileobj, size: int):
        """
        Uploads a file to the specified S3 bucket as it is read. boto3 reads a file that cannot
        seek a part at a time, sending parts in parallel while it reads the next. Files smaller
        than one part are sent in a single PUT. If the upload fails, boto3 aborts it.

        Blocks until the upload is complete, so call it in a thread.

        :param bucket: S3 bucket to upload to
        :param key: Name of the object
        :param content_type: Content type of the object, if known
        :param fileobj: The file, which needs only a read() method
        :param size: Size of the file in bytes (an upper bound will do), used to choose the
            part size
        """
        check_object_size(size)
        part_size = stream_part_size(size)
        config = TransferConfig(
            multipart_threshold=part_size,
            multipart_chunksize=part_size,
            max_concurrency=STREAM_CONCURRENCY,
            # The CRT client handles streams differently, so make sure the classic one is used
            preferred_transfer_client="classic",
        )
        # Not a TransferConfig argument, but how many parts boto3 holds in memory at once
        config.max_in_memory_upload_chunks = STREAM_CONCURRENCY
        try:
            self.client.upload_fileobj(
                fileobj,
                bucket,
                key,
                ExtraArgs={"ContentType": content_type} if content_type else None,
                Config=config,
            )
        except (HTTPException, ClientDisconnect):
            raise
        except ClientError as error:
            self.handle_s3_error(error)
        except Exception as error:
            raise HTTPException(
                status_code=500, detail=f"Unable to upload object: {error}"
            ) from error

        return {
            "status": 201,
            "response": key,
        }

    def get_object(self, bucket, file_name, target_file=None):
        """
        Retrieves an object from the specified S3 bucket.

        :param bucket: S3 bucket to retrieve the object from
        :param file_name: Name of the object to retrieve
        :param target_file: Optional file to save the retrieved object to
        """
        try:
            response = self.client.get_object(Bucket=bucket, Key=file_name)
            if not target_file:
                target_file = file_name
            # Read in 1MiB chunks: iterating over the body directly gives 1KiB chunks, each
            # fetched in a separate thread-pool call
            return StreamingResponse(
                response["Body"].iter_chunks(MiB),
                media_type=response.get("ContentType", "application/octet-stream"),
                headers={
                    "Content-Disposition": f'attachment; filename="{target_file}"',
                    "Content-Length": str(response["ContentLength"]),
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

    def check_object_exists(self, bucket, file_name):
        """
        Checks if an object exists in the specified S3 bucket.

        :param bucket: S3 bucket to check the object in
        :param file_name: Name of the object to check
        :return: True if the object exists, False otherwise
        """
        # Uses a listing rather than head_object so that only List permission is needed,
        # as the API's generic identity cannot read the ingress bucket
        try:
            response = self.client.list_objects_v2(
                Bucket=bucket, Prefix=file_name, MaxKeys=1
            )
        except ClientError as error:
            self.handle_s3_error(error)
            return False
        return any(obj["Key"] == file_name for obj in response.get("Contents", []))

    def delete_object(self, bucket, file_name):
        """
        Deletes an object from the specified S3 bucket.

        :param bucket: S3 bucket to delete the object from
        :param file_name: Name of the object to delete
        """
        try:
            self.client.delete_object(Bucket=bucket, Key=file_name)
            return {
                "status": 200,
                "response": f"Object {file_name} deleted from {bucket}",
            }
        except ClientError as error:
            self.handle_s3_error(error)
