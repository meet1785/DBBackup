"""Cloud storage support (AWS S3, Google Cloud Storage, Azure Blob Storage)."""

import logging
import os

logger = logging.getLogger("db_backup")


def upload_to_s3(file_path: str, bucket: str, key: str | None = None, region: str | None = None) -> str:
    """Upload a backup file to AWS S3.

    Uses credentials from environment variables or ~/.aws/credentials.

    Args:
        file_path: Local path to the file to upload.
        bucket: S3 bucket name.
        key: Object key (defaults to the filename).
        region: AWS region (optional).

    Returns:
        The S3 URI of the uploaded object.
    """
    try:
        import boto3
    except ImportError:
        raise RuntimeError("boto3 is required for S3 uploads. Install it with: pip install boto3")

    if key is None:
        key = os.path.basename(file_path)

    logger.info("Uploading %s to s3://%s/%s ...", os.path.basename(file_path), bucket, key)

    session_kwargs = {}
    if region:
        session_kwargs["region_name"] = region

    s3 = boto3.client("s3", **session_kwargs)
    s3.upload_file(file_path, bucket, key)

    s3_uri = f"s3://{bucket}/{key}"
    logger.info("Upload complete: %s", s3_uri)
    return s3_uri


def download_from_s3(bucket: str, key: str, dest_path: str, region: str | None = None) -> str:
    """Download a backup file from AWS S3.

    Args:
        bucket: S3 bucket name.
        key: Object key in the bucket.
        dest_path: Local path to save the downloaded file.
        region: AWS region (optional).

    Returns:
        The local path of the downloaded file.
    """
    try:
        import boto3
    except ImportError:
        raise RuntimeError("boto3 is required for S3 downloads. Install it with: pip install boto3")

    logger.info("Downloading s3://%s/%s ...", bucket, key)

    session_kwargs = {}
    if region:
        session_kwargs["region_name"] = region

    s3 = boto3.client("s3", **session_kwargs)
    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
    s3.download_file(bucket, key, dest_path)

    logger.info("Downloaded to %s", dest_path)
    return dest_path
