from fastapi import File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from io import BytesIO
from minio import Minio, versioningconfig, commonconfig
from minio.error import S3Error
from pathlib import Path
from threading import Lock

import os
import ssl
import urllib3
import xml.etree.ElementTree as ET


class MinioClient:
    SA_TOKEN_FILE = os.getenv("MINIO_SA_TOKEN_PATH", "/minio/token")
    # Kube CA cert path added by mounted service account, needed for TLS with Minio STS
    KUBE_CA_CRT = os.getenv(
        "STS_CA_CERT_FILE", "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
    )

    def __init__(
        self,
        endpoint: str,
        sts_endpoint: str | None = None,
        tenant: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        secure: bool = False,
    ):
        self.endpoint = endpoint
        self.sts_endpoint = sts_endpoint
        self.tenant = tenant
        self.secure = secure
        self.refresh_lock = Lock()

        retry_count = 0
        st = None  # Default session token to None if not using STS

        # Try STS auth if access or secret key is not defined
        while (access_key is None or secret_key is None) and retry_count < 5:
            print("Attempting Minio authentication with STS")
            retry_count = retry_count + 1
            try:
                access_key, secret_key, st = self.handle_sts_auth()
            except Exception as e:
                print(f"Failed to get keys for minio client: {e}")

        # Exit if minio client keys are not available
        if access_key is None or secret_key is None:
            print("Failed to initialise Minio client")
            exit(1)

        self._create_client(access_key, secret_key, st)
        print("Successfully configured Minio client")

    def _create_client(
        self, access_key: str, secret_key: str, session_token: str | None
    ) -> Minio:
        self.client = Minio(
            self.endpoint,
            access_key=access_key,
            secret_key=secret_key,
            session_token=session_token,
            secure=self.secure,
        )

    def handle_sts_auth(self):
        """Handle STS authentication with MinIO using Kubernetes service account token."""

        # Set the environment variable for minio client to use the k8s certificate
        os.environ["SSL_CERT_FILE"] = self.KUBE_CA_CRT

        # Read service account token
        sa_token = Path(self.SA_TOKEN_FILE).read_text().strip()

        # Cache the token used here for change detection
        self._last_token = sa_token

        ssl_context = ssl.create_default_context(cafile=self.KUBE_CA_CRT)

        # Create urllib3 client which accepts kube CA cert
        http = urllib3.PoolManager(ssl_context=ssl_context)

        # Send the token to the MinIO STS endpoint
        response = http.request(
            "POST",
            f"{self.sts_endpoint}/sts/{self.tenant}?Action=AssumeRoleWithWebIdentity&Version=2011-06-15&WebIdentityToken={sa_token}",
        )

        if response.status != 200:
            print(f"STS request failed: {response.status} {response.data.decode()}")
            return None, None, None
        else:
            root = ET.fromstring(response.data)
            ns = {"sts": "https://sts.amazonaws.com/doc/2011-06-15/"}
            credentials = root.find(".//sts:Credentials", ns)
            access_key = credentials.find("sts:AccessKeyId", ns).text
            secret_key = credentials.find("sts:SecretAccessKey", ns).text
            session_token = credentials.find("sts:SessionToken", ns).text

            return access_key, secret_key, session_token

    def _token_has_changed(self):
        """Check if the service account token has changed since last read."""
        try:
            current_token = Path(self.SA_TOKEN_FILE).read_text().strip()
            return current_token != self._last_token
        except Exception as e:
            print(f"Error reading token file: {e}")
            return False

    def _refresh_token(self):
        """Refresh the service account token and update the Minio client session token."""
        with self.refresh_lock:
            if not self._token_has_changed():
                return  # No change in token so refresh unnecessary
            print("Refreshing Minio client session token")
            try:
                access_key, secret_key, session_token = self.handle_sts_auth()

                if access_key and secret_key:
                    self.client = self._create_client(
                        access_key, secret_key, session_token
                    )
                    print("Minio client token refreshed successfully")
                else:
                    print("Failed to refresh Minio client token")
            except Exception as e:
                print(f"Failed to refresh Minio client token: {e}")
                raise HTTPException(
                    status_code=500, detail="Failed to refresh Minio token"
                )

    def _ensure_valid_token(self):
        """Check if the token needs to be refreshed"""
        if self._token_has_changed():
            self._refresh_token()

    def handle_minio_error(self, error: S3Error):
        if error._code in ["NoSuchBucket", "NoSuchKey"]:
            status = 404
        elif error._code in ["AccessDenied"]:
            status = 403
        else:
            status = 500

        raise HTTPException(status_code=status, detail=error.message)

    def create_bucket(self, name, enable_versioning=False):
        self._ensure_valid_token()
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
            raise HTTPException(status_code=500, detail="Unable to create bucket")

        return {"response": name, "status": 201}

    async def put_object(self, bucket, file: UploadFile = File(...)):
        self._ensure_valid_token()
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
            self.handle_minio_error(error)
        except Exception as error:
            raise HTTPException(
                status_code=500, detail=f"Unable to upload object: {error}"
            )

        return {
            "status": 201,
            "response": result._location,
            "version": result.version_id,
        }

    def get_object(self, bucket, file_name, target_file=None, version=None):
        self._ensure_valid_token()
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
            self.handle_minio_error(error)
        except Exception as error:
            raise HTTPException(
                status_code=500, detail=f"Unable to get object from bucket: {error}"
            )

    def check_object_exists(self, bucket, file_name, version=None):
        self._ensure_valid_token()
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
        self._ensure_valid_token()
        try:
            # Check that the object exists in the bucket before deleting
            if self.check_object_exists(bucket, file_name, version):
                self.client.remove_object(bucket, file_name, version_id=version)
            else:
                return {
                    "status": 404,
                    "response": f"{file_name} not found in {bucket}",
                    "version": version,
                }
        except S3Error as error:
            self.handle_minio_error(error)
        except Exception as error:
            raise HTTPException(
                status_code=500, detail="Unable to delete object from bucket"
            )

        return {"status": 200, "response": file_name, "version": version}
