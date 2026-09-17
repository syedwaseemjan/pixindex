from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pixindex.metadata import EXTENSIONS

JPEG_RANGE = (0, 64 * 1024 - 1)


class S3Error(Exception):
    """Problem talking to S3 or reading an s3:// URI."""


@dataclass(frozen=True)
class S3Object:
    bucket: str
    key: str
    size: int
    etag: str


class ObjectStore(Protocol):
    def list_images(self, bucket: str, prefix: str) -> list[S3Object]: ...

    def get_bytes(
        self, obj: S3Object, byte_range: tuple[int, int] | None = None
    ) -> bytes: ...


def parse_s3_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("s3://"):
        raise S3Error(f"Not an s3:// URI: {uri}")
    rest = uri[5:]
    bucket, sep, prefix = rest.partition("/")
    if not bucket:
        raise S3Error("s3:// URI needs a bucket name.")
    if not sep:
        prefix = ""
    return bucket, prefix


def normalize_s3_source(bucket: str, prefix: str) -> str:
    prefix = prefix.strip("/")
    if prefix:
        return f"s3://{bucket}/{prefix}"
    return f"s3://{bucket}"


def clean_etag(value: str) -> str:
    return value.strip().strip('"')


def is_image_key(key: str) -> bool:
    if key.endswith("/"):
        return False
    name = key.rsplit("/", 1)[-1]
    if name.startswith("."):
        return False
    return Path(name).suffix.lower() in EXTENSIONS


class BotoS3Store:
    def __init__(self, client=None) -> None:
        self.client = client if client is not None else _client()

    def list_images(self, bucket: str, prefix: str) -> list[S3Object]:
        from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

        objects: list[S3Object] = []
        try:
            paginator = self.client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for item in page.get("Contents") or []:
                    key = item["Key"]
                    if not is_image_key(key):
                        continue
                    objects.append(
                        S3Object(
                            bucket=bucket,
                            key=key,
                            size=int(item["Size"]),
                            etag=clean_etag(str(item["ETag"])),
                        )
                    )
        except NoCredentialsError as exc:
            raise S3Error(
                "No AWS credentials. Set AWS_PROFILE or AWS_ACCESS_KEY_ID."
            ) from exc
        except (ClientError, BotoCoreError) as exc:
            raise S3Error(f"Could not list s3://{bucket}/{prefix}: {exc}") from exc
        return objects

    def get_bytes(
        self, obj: S3Object, byte_range: tuple[int, int] | None = None
    ) -> bytes:
        from botocore.exceptions import BotoCoreError, ClientError

        request = {"Bucket": obj.bucket, "Key": obj.key}
        if byte_range is not None:
            start, end = byte_range
            request["Range"] = f"bytes={start}-{end}"
        try:
            return self.client.get_object(**request)["Body"].read()
        except (ClientError, BotoCoreError) as exc:
            raise S3Error(f"Could not read s3://{obj.bucket}/{obj.key}: {exc}") from exc


def _client():
    import boto3

    return boto3.client("s3")
