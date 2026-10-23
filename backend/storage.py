import io
from typing import BinaryIO, Union
from datetime import timedelta
from minio import Minio
from minio.error import S3Error
from config import get_settings

settings = get_settings()


class FileStorage:
    def __init__(self):
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self.bucket = settings.minio_bucket

    def upload_file(self, storage_key: str, data: BinaryIO, length: int, content_type: str = "application/octet-stream"):
        self.client.put_object(
            self.bucket,
            storage_key,
            data,
            length,
            content_type=content_type,
        )

    def download_file(self, storage_key: str) -> bytes:
        response = self.client.get_object(self.bucket, storage_key)
        data = response.read()
        response.close()
        response.release_conn()
        return data

    def get_presigned_url(self, storage_key: str, expires: Union[int, timedelta] = 3600) -> str:
        delta = expires if isinstance(expires, timedelta) else timedelta(seconds=expires)
        return self.client.presigned_get_object(self.bucket, storage_key, expires=delta)

    def delete_file(self, storage_key: str):
        try:
            self.client.remove_object(self.bucket, storage_key)
        except S3Error:
            pass


storage = FileStorage()
