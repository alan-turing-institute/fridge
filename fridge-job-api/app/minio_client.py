from fastapi import File, UploadFile
from minio import Minio, versioningconfig, commonconfig
from io import BytesIO
from minio.error import S3Error


class MinioClient:
    def __init__(self, endpoint: str, access_key: str, secret_key: str):
        self.client = Minio(
            endpoint, access_key=access_key, secret_key=secret_key, secure=False
        )

    def handle_minio_error(self, error: S3Error):
        status = 500
        if error._code in ["NoSuchBucket", "NoSuchKey"]:
            status = 404
        return {"response": error._message, "error": error, "status": status}

    def handle_500_error(self, msg=""):
        return {"status": 500, "response": f"Unexpected error: {msg}"}

    def create_bucket(self, name, enable_versioning=False):
        try:
            if not self.client.bucket_exists(name):
                self.client.make_bucket(name)

            if enable_versioning:
                self.client.set_bucket_versioning(
                    name, versioningconfig.VersioningConfig(commonconfig.ENABLED)
                )
        except S3Error as error:
            self.handle_minio_error(error)
        except ValueError as error:
            self.handle_500_error("Unable to create bucket")

        return {"response": name, "status": 201}

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
        except S3Error as error:
            return self.handle_minio_error(error)
        except Exception as error:
            self.handle_500_error("Unable to upload object")

        return {
            "status": 201,
            "response": result._location,
            "version": result.version_id,
        }

    def get_object(self, bucket, file_name, target_file, version=None):
        try:
            result = self.client.fget_object(bucket, file_name, target_file, version)
        except S3Error as error:
            return self.handle_minio_error(error)
        except Exception as error:
            self.handle_500_error("Unable to get object from bucket")

        return {"response": target_file, "version": result.version_id}

    def check_object_exists(self, bucket, file_name, version=None):
        try:
            self.client.stat_object(bucket, file_name, version_id=version)
            return True
        # Raise not-found error to be caught and returned by upstream function
        except S3Error as error:
            raise error
        # Handle all other exceptions as object does not exist
        except Exception as error:
            return False

    def delete_object(self, bucket, file_name, version=None):
        try:
            # Check that the object exists in the bucket before deleting
            if self.check_object_exists(bucket, file_name, version):
                self.client.remove_object(bucket, file_name, version_id=version)
            else:
                # Use this path if stat_object result could not be determined
                return {"status": 500, "response": "Object not deleted"}
        except S3Error as error:
            return self.handle_minio_error(error)
        except Exception as error:
            self.handle_500_error("Unable to delete object from bucket")

        return {"status": 200, "response": file_name, "version": version}
