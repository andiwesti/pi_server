#!/usr/bin/env python3
# storage.py – S3 presigned helpers

import os
import uuid
import mimetypes
import boto3

S3_BUCKET = os.getenv("S3_BUCKET", "pi-photos-bucket")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "eu-north-1")

s3 = boto3.client("s3", region_name=AWS_REGION)


def _guess_content_type(filename: str) -> str:
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"


def create_presigned_upload_url(data: dict) -> dict:
    """Create presigned S3 upload and view URLs."""
    filename = (data or {}).get("filename") or f"{uuid.uuid4()}.bin"
    content_type = (data or {}).get("contentType") or _guess_content_type(filename)
    user_id = (data or {}).get("userId") or "anon"
    key = f"users/{user_id}/{uuid.uuid4()}-{filename}"

    upload_url = s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={"Bucket": S3_BUCKET, "Key": key, "ContentType": content_type},
        ExpiresIn=600,   # 10 minutes
        HttpMethod="PUT",
    )

    view_url = s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": S3_BUCKET, "Key": key},
        ExpiresIn=3600,  # 1 hour
    )

    return {"uploadUrl": upload_url, "key": key, "viewUrl": view_url}


def create_presigned_view_url(data: dict) -> dict:
    """Create presigned view URL for an S3 object."""
    key = (data or {}).get("key")
    if not key:
        raise ValueError("Missing 'key'")
    url = s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": S3_BUCKET, "Key": key},
        ExpiresIn=3600,
    )
    return {"url": url}

def list_s3_objects(prefix="users/") -> dict:
    """List objects in the S3 bucket with optional prefix."""
    resp = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix, MaxKeys=100)
    items = []
    for o in resp.get("Contents", []):
        items.append({
            "key": o["Key"],
            "size": o.get("Size", 0),
            "lastModified": o.get("LastModified").isoformat(),
        })
    return {
        "items": items,
        "truncated": resp.get("IsTruncated", False)
    }

