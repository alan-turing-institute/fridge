from fastapi import HTTPException, File, UploadFile
from minio import Minio
from io import BytesIO
from minio.error import S3Error


class MinioClient():
    def __init__(self, endpoint: str, access_key: str, secret_key: str):
        self.client = Minio(
            endpoint, access_key=access_key, secret_key=secret_key, secure=False
        )

    def parse_minio_error(self, data):
        print(data)

    def create_bucket(self, name):
        try:
            if not self.client.bucket_exists(name):
                self.client.make_bucket(name)
        except S3Error as error:
            return {
                "response": error._message,
                "code": error._code,
                "status": 500
            }
        except ValueError as error:
            return {
                "response": str(error),
                "status": 500
            }

        return {
            "response": name,
            "status": 201
        }

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
            return {
                "response": error._message,
                "code": error._code,
                "status": 500
            }

        return {
            "status": 201,
            "response": result._location
        }

    def get_object(self, bucket, file_name, target_file):
        try:
            self.client.fget_object(bucket, file_name, target_file)
        except S3Error as error:
            status = 500
            # Return 404 if bucket or object does not exist
            if error._code in ["NoSuchBucket", "NoSuchKey"]:
                status = 404
            return {
                "response": error._message,
                "code": error._code,
                "status": status
            }

        return {
            "response": target_file
        }
    