from fastapi import File, UploadFile
from fastapi.responses import StreamingResponse
from minio import Minio, versioningconfig, commonconfig
from io import BytesIO
from minio.error import S3Error
import urllib3
from pathlib import Path
import xml.etree.ElementTree as ET

class MinioClient:
    def __init__(self, endpoint: str, sts_endpoint: str):
        access_key, secret_key = self.get_credentials(sts_endpoint)
        self.client = Minio(
            endpoint, access_key=access_key, secret_key=secret_key, secure=False
        )

    def get_credentials(self, sts_endpoint):
        SA_TOKEN_FILE = "/minio/token"      # Path to the service account token
        # CA_FILE = "kube-ca.crt"             # Kubernetes CA file

        # Read service account token
        sa_token = Path(SA_TOKEN_FILE).read_text().strip()

        # Create urllib3 client
        http = urllib3.PoolManager()

        # Send the token to the MinIO STS endpoint
        response = http.request(
            "POST",
            f"{sts_endpoint}/sts/argo-artifacts?Action=AssumeRoleWithWebIdentity&Version=2011-06-15&WebIdentityToken={sa_token}",
        )

        if response.status != 200:
            return self.handle_500_error(msg=response.data.decode())
        else:
            root = ET.fromstring(response.data)
            ns = {'sts': 'https://sts.amazonaws.com/doc/2011-06-15/'}
            credentials = root.find(".//sts:Credentials", ns)
            access_key = credentials.find('sts:AccessKeyId', ns).text
            secret_key = credentials.find('sts:SecretAccessKey', ns).text
            
            return access_key, secret_key


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
            return self.handle_minio_error(error)
        except ValueError as error:
            return self.handle_500_error("Unable to create bucket")

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
            return self.handle_500_error("Unable to upload object")

        return {
            "status": 201,
            "response": result._location,
            "version": result.version_id,
        }

    def get_object(self, bucket, file_name, target_file=None, version=None):
        if not target_file:
            target_file = file_name
        try:
            result = self.client.get_object(bucket, file_name, target_file, version)
            return StreamingResponse(
                result,
                media_type="application/octet-stream",
                headers={
                    "Content-Disposition": f'attachment; filename="{target_file}"'
                },
            )
        except S3Error as error:
            return self.handle_minio_error(error)
        except Exception as error:
            return self.handle_500_error("Unable to get object from bucket")

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
            return self.handle_500_error("Unable to delete object from bucket")

        return {"status": 200, "response": file_name, "version": version}
