"""Private S3-compatible object storage for Soil Health Card images."""

import asyncio
from typing import Protocol

from config.settings import settings


class ObjectStoreUnavailable(RuntimeError):
    pass


class ObjectStore(Protocol):
    async def put(self, key: str, data: bytes, content_type: str, sha256: str) -> None: ...
    async def get(self, key: str) -> bytes: ...
    async def signed_read_url(self, key: str, expires_seconds: int = 300) -> str: ...
    async def delete(self, key: str) -> None: ...


class S3PrivateObjectStore:
    def __init__(self) -> None:
        if not all((settings.object_storage_bucket, settings.object_storage_access_key_id,
                    settings.object_storage_secret_access_key)):
            raise ObjectStoreUnavailable("Private soil-card object storage is not configured")
        try:
            import boto3
        except ImportError as exc:
            raise ObjectStoreUnavailable("boto3 is required for private object storage") from exc
        self.bucket = settings.object_storage_bucket
        try:
            self.client = boto3.client(
                "s3", endpoint_url=settings.object_storage_endpoint_url,
                region_name=settings.object_storage_region,
                aws_access_key_id=settings.object_storage_access_key_id,
                aws_secret_access_key=settings.object_storage_secret_access_key.get_secret_value(),
                use_ssl=settings.object_storage_secure,
            )
        except Exception as exc:
            raise ObjectStoreUnavailable("Private object storage is unavailable") from exc

    async def put(self, key: str, data: bytes, content_type: str, sha256: str) -> None:
        try:
            await asyncio.to_thread(self.client.put_object, Bucket=self.bucket, Key=key, Body=data,
                                    ContentType=content_type, ServerSideEncryption="AES256",
                                    Metadata={"sha256": sha256})
        except Exception as exc:
            raise ObjectStoreUnavailable("Private object storage write failed") from exc

    async def get(self, key: str) -> bytes:
        try:
            result = await asyncio.to_thread(self.client.get_object, Bucket=self.bucket, Key=key)
            return await asyncio.to_thread(result["Body"].read)
        except Exception as exc:
            raise ObjectStoreUnavailable("Private object storage read failed") from exc

    async def signed_read_url(self, key: str, expires_seconds: int = 300) -> str:
        try:
            return await asyncio.to_thread(self.client.generate_presigned_url, "get_object",
                                           Params={"Bucket": self.bucket, "Key": key},
                                           ExpiresIn=expires_seconds)
        except Exception as exc:
            raise ObjectStoreUnavailable("Signed image URL could not be created") from exc

    async def delete(self, key: str) -> None:
        try:
            await asyncio.to_thread(self.client.delete_object, Bucket=self.bucket, Key=key)
        except Exception as exc:
            raise ObjectStoreUnavailable("Private object storage delete failed") from exc


class UnavailableObjectStore:
    def __init__(self, reason: str):
        self.reason = reason

    async def put(self, key: str, data: bytes, content_type: str, sha256: str) -> None:
        raise ObjectStoreUnavailable(self.reason)

    async def get(self, key: str) -> bytes:
        raise ObjectStoreUnavailable(self.reason)

    async def signed_read_url(self, key: str, expires_seconds: int = 300) -> str:
        raise ObjectStoreUnavailable(self.reason)

    async def delete(self, key: str) -> None:
        raise ObjectStoreUnavailable(self.reason)


def get_object_store() -> ObjectStore:
    try:
        return S3PrivateObjectStore()
    except ObjectStoreUnavailable as exc:
        return UnavailableObjectStore(str(exc))
