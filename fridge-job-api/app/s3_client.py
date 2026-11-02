import asyncio
import boto3
import os
from botocore.client import Config
from botocore.exceptions import ClientError
from collections.abc import AsyncIterator
from contextlib import contextmanager
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool


MiB = 1024 * 1024
GiB = 1024 * MiB
TiB = 1024 * GiB
# The largest object that can be uploaded, either in a single request or part by part
MAX_OBJECT_SIZE = 1 * TiB
# S3 allows at most 10,000 parts in a multipart upload
MAX_PART_COUNT = 10_000
# Smallest part size for files sent in a single request. Small enough that mid-sized files
# are still sent to S3 as several parts in parallel
STREAM_PART_SIZE = 16 * MiB
STREAM_CONCURRENCY = 4
# Smallest part size for uploads the client sends part by part
UPLOAD_PART_SIZE = 64 * MiB
# Total upload data the API holds in memory at once, across all requests
UPLOAD_MEMORY_BUDGET = 1 * GiB


def part_size_for(size: int, minimum: int) -> int:
    """
    The part size to use for an object of `size` bytes: at least `minimum`, and large enough,
    in whole MiB, for the object to fit in MAX_PART_COUNT parts.
    """
    needed = -(-size // MAX_PART_COUNT)
    return max(minimum, -(-needed // MiB) * MiB)


# The largest part needed for an object of MAX_OBJECT_SIZE (105MiB)
MAX_PART_SIZE = part_size_for(MAX_OBJECT_SIZE, UPLOAD_PART_SIZE)


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


def _completed_part(number: int, part: dict) -> dict:
    """A part entry for CompleteMultipartUpload, carrying any checksum S3 returned for it."""
    return {
        "PartNumber": number,
        **{k: v for k, v in part.items() if k == "ETag" or k.startswith("Checksum")},
    }


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

    async def put_object(
        self,
        bucket,
        key,
        content_type,
        chunks: AsyncIterator[bytes],
        size: int,
    ):
        """
        Uploads a file to the specified S3 bucket as its data arrives. Small files are sent in a
        single PUT. Larger files are sent as a multipart upload, with parts sent in parallel
        while the rest of the file is still arriving.

        The memory the upload can use, up to STREAM_CONCURRENCY + 1 parts, is reserved before
        any data is read, so that a long upload is never refused partway through.

        :param bucket: S3 bucket to upload to
        :param key: Name of the object
        :param content_type: Content type of the object, if known
        :param chunks: The file's contents
        :param size: Size of the file in bytes, used to choose the part size
        """
        check_object_size(size)
        part_size = part_size_for(size, STREAM_PART_SIZE)
        with upload_memory.reserve(min(size, part_size * (STREAM_CONCURRENCY + 1))):
            return await self._put_object(bucket, key, content_type, chunks, part_size)

    async def _put_object(self, bucket, key, content_type, chunks, part_size):
        extra_args = {"ContentType": content_type} if content_type else {}
        buffer = bytearray()
        upload_id = None
        uploads: list[asyncio.Task] = []
        # Limits how many parts are held in memory waiting to be sent
        slots = asyncio.Semaphore(STREAM_CONCURRENCY)

        async def send_part(number, body):
            try:
                response = await run_in_threadpool(
                    self.client.upload_part,
                    Bucket=bucket,
                    Key=key,
                    UploadId=upload_id,
                    PartNumber=number,
                    Body=body,
                )
                return _completed_part(number, response)
            finally:
                slots.release()

        async def start_part(body):
            nonlocal upload_id
            if upload_id is None:
                response = await run_in_threadpool(
                    self.client.create_multipart_upload,
                    Bucket=bucket,
                    Key=key,
                    **extra_args,
                )
                upload_id = response["UploadId"]
            await slots.acquire()
            # Stop reading the request as soon as a part has failed
            for task in uploads:
                if task.done() and task.exception():
                    raise task.exception()
            uploads.append(asyncio.create_task(send_part(len(uploads) + 1, body)))

        try:
            async for chunk in chunks:
                buffer += chunk
                while len(buffer) >= part_size:
                    await start_part(bytes(buffer[:part_size]))
                    del buffer[:part_size]
            if upload_id is None:
                await run_in_threadpool(
                    self.client.put_object,
                    Bucket=bucket,
                    Key=key,
                    Body=buffer,
                    **extra_args,
                )
            else:
                if buffer:
                    await start_part(buffer)
                parts = await asyncio.gather(*uploads)
                await run_in_threadpool(
                    self.client.complete_multipart_upload,
                    Bucket=bucket,
                    Key=key,
                    UploadId=upload_id,
                    MultipartUpload={"Parts": parts},
                )
        except Exception as error:
            for task in uploads:
                task.cancel()
            await asyncio.gather(*uploads, return_exceptions=True)
            if upload_id is not None:
                await run_in_threadpool(self._abort_quietly, bucket, key, upload_id)
            if isinstance(error, HTTPException):
                raise
            if isinstance(error, ClientError):
                self.handle_s3_error(error)
            raise HTTPException(
                status_code=500, detail=f"Unable to upload object: {error}"
            ) from error

        return {
            "status": 201,
            "response": key,
        }

    def _abort_quietly(self, bucket, key, upload_id):
        """Aborts a multipart upload after a failure, without masking the original error."""
        try:
            self.client.abort_multipart_upload(
                Bucket=bucket, Key=key, UploadId=upload_id
            )
        except ClientError:
            pass

    def create_multipart_upload(self, bucket, key, size, content_type=None):
        """
        Starts a multipart upload that the client sends part by part, so that it can send parts
        in parallel and resume after an interruption.

        :param bucket: S3 bucket to upload to
        :param key: Name of the object
        :param content_type: Content type of the object, if known
        :param size: Size of the file in bytes, used to choose the part size
        :return: The upload ID and the part size the client should use
        """
        check_object_size(size)
        part_size = part_size_for(size, UPLOAD_PART_SIZE)
        extra_args = {"ContentType": content_type} if content_type else {}
        try:
            response = self.client.create_multipart_upload(
                Bucket=bucket, Key=key, **extra_args
            )
        except ClientError as error:
            self.handle_s3_error(error)
        return {
            "upload_id": response["UploadId"],
            "key": key,
            "part_size": part_size,
        }

    def upload_part(self, bucket, key, upload_id, part_number, body: bytes | bytearray):
        """
        Uploads one part of a multipart upload. Uploading a part number again replaces it.

        :param part_number: Number of the part, from 1 to 10,000
        :param body: Contents of the part
        """
        try:
            response = self.client.upload_part(
                Bucket=bucket,
                Key=key,
                UploadId=upload_id,
                PartNumber=part_number,
                Body=body,
            )
        except ClientError as error:
            self.handle_s3_error(error)
        return {
            "part_number": part_number,
            "etag": response["ETag"],
            "size": len(body),
        }

    def _list_parts(self, bucket, key, upload_id) -> list[dict]:
        paginator = self.client.get_paginator("list_parts")
        parts = []
        for page in paginator.paginate(Bucket=bucket, Key=key, UploadId=upload_id):
            parts.extend(page.get("Parts", []))
        return parts

    def list_parts(self, bucket, key, upload_id):
        """
        Lists the parts of a multipart upload that S3 already has, so that an interrupted
        upload can be resumed by sending only the missing parts.
        """
        try:
            parts = self._list_parts(bucket, key, upload_id)
        except ClientError as error:
            self.handle_s3_error(error)
        return {
            "upload_id": upload_id,
            "key": key,
            "parts": [
                {"part_number": p["PartNumber"], "etag": p["ETag"], "size": p["Size"]}
                for p in parts
            ],
        }

    def complete_multipart_upload(self, bucket, key, upload_id, part_count):
        """
        Joins the parts of a multipart upload into the final object.

        :param part_count: Number of parts the client sent. The upload is only completed if
            S3 has exactly parts 1 to part_count, so a file with missing parts is never stored
        """
        try:
            parts = self._list_parts(bucket, key, upload_id)
            numbers = [p["PartNumber"] for p in parts]
            if numbers != list(range(1, part_count + 1)):
                missing = sorted(set(range(1, part_count + 1)) - set(numbers))
                raise HTTPException(
                    status_code=409,
                    detail=f"Expected parts 1 to {part_count}. Missing parts: {missing}. Unexpected parts: {sorted(set(numbers) - set(range(1, part_count + 1)))}",
                )
            self.client.complete_multipart_upload(
                Bucket=bucket,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={
                    "Parts": [_completed_part(p["PartNumber"], p) for p in parts]
                },
            )
        except ClientError as error:
            self.handle_s3_error(error)
        return {
            "status": 201,
            "response": key,
        }

    def abort_multipart_upload(self, bucket, key, upload_id):
        """Abandons a multipart upload, discarding the parts already sent."""
        try:
            self.client.abort_multipart_upload(
                Bucket=bucket, Key=key, UploadId=upload_id
            )
        except ClientError as error:
            self.handle_s3_error(error)
        return {
            "status": 200,
            "response": f"Upload {upload_id} of {key} to {bucket} aborted",
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
