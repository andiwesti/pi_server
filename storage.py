# storage.py
import os
import uuid
import boto3
import mimetypes

S3_BUCKET  = os.getenv("S3_BUCKET", "pi-photos-bucket")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "eu-north-1")
s3 = boto3.client("s3", region_name=AWS_REGION)

def guess_content_type(filename: str):
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"

def key_for(user_id: str, filename: str) -> str:
    base = filename or f"{uuid.uuid4()}.bin"
    return f"users/{user_id}/{uuid.uuid4()}-{base}"

def presign_put(key: str, content_type: str, expires=600) -> str:
    return s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={"Bucket": S3_BUCKET, "Key": key, "ContentType": content_type},
        ExpiresIn=expires,
        HttpMethod="PUT",
    )

def presign_get(key: str, expires=3600) -> str:
    return s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": S3_BUCKET, "Key": key},
        ExpiresIn=expires,
    )

def upload_bytes(key: str, data: bytes, content_type="application/octet-stream"):
    import io
    s3.upload_fileobj(io.BytesIO(data), S3_BUCKET, key, ExtraArgs={"ContentType": content_type})
