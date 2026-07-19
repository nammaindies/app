import aioboto3
from botocore.exceptions import ClientError

from app.config import settings


class S3Storage:
    def __init__(
        self,
        *,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: str,
    ) -> None:
        self.endpoint = endpoint
        self.bucket = bucket
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self._session = aioboto3.Session()

    def _client(self):
        return self._session.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
        )

    async def ensure_bucket(self) -> None:
        async with self._client() as client:
            try:
                await client.head_bucket(Bucket=self.bucket)
                return
            except ClientError:
                pass

            try:
                await client.create_bucket(Bucket=self.bucket)
            except ClientError as e:
                code = e.response.get("Error", {}).get("Code", "")
                if code in (
                    "BucketAlreadyOwnedByYou",
                    "BucketAlreadyExists",
                ):
                    return
                raise

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        async with self._client() as client:
            await client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )

    async def list_keys(self, prefix: str) -> list[str]:
        async with self._client() as client:
            keys: list[str] = []
            paginator = client.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    keys.append(obj["Key"])
            return keys

    async def url(self, key: str, expires_s: int = 3600) -> str:
        async with self._client() as client:
            return await client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires_s,
            )


def storage_from_settings() -> S3Storage:
    return S3Storage(
        endpoint=settings.s3_endpoint,
        bucket=settings.s3_bucket,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        region=settings.s3_region,
    )
