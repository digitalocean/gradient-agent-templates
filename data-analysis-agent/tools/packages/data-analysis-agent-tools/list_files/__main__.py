import boto3
import os
import logging
from typing import Dict, Any, List
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    List all CSV files available in the Spaces bucket with their metadata.

    Args:
        args: Dictionary (no parameters required)

    Returns:
        Dictionary with list of CSV files and their metadata
    """
    logger.info("=" * 50)
    logger.info("🔍 LIST_FILES TOOL CALLED")
    logger.info("=" * 50)
    logger.info(f"Input args: {args}")

    try:
        # Get Spaces credentials from environment
        logger.info("Getting Spaces credentials from environment...")
        access_key = os.getenv("SPACES_ACCESS_KEY")
        secret_key = os.getenv("SPACES_SECRET_KEY")
        bucket_name = os.getenv("SPACES_BUCKET")
        region = os.getenv("SPACES_REGION")

        logger.info(f"Spaces config - Bucket: {bucket_name}, Region: {region}")
        logger.info(f"Access key present: {bool(access_key)}")
        logger.info(f"Secret key present: {bool(secret_key)}")

        if not all([access_key, secret_key, bucket_name, region]):
            error_msg = "Missing Spaces configuration"
            logger.error(f"❌ {error_msg}")
            return {"body": {"success": False, "error": error_msg}}

        # Create S3 client for Spaces
        logger.info("Creating S3 client for DigitalOcean Spaces...")
        session = boto3.session.Session()
        s3_client = session.client(
            "s3",
            region_name=region,
            endpoint_url=f"https://{region}.digitaloceanspaces.com",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        logger.info("S3 client created successfully")

        # List objects in the bucket
        logger.info(f"Listing objects in bucket: {bucket_name}")
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        logger.info(f"S3 response keys: {list(response.keys())}")

        files = []
        if "Contents" in response:
            logger.info(f"Found {len(response['Contents'])} objects in bucket")
            for obj in response["Contents"]:
                key = obj["Key"]
                logger.info(f"Processing object: {key}")
                # Only include CSV files
                if key.lower().endswith(".csv"):
                    file_info = {
                        "filename": key,
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"].isoformat(),
                    }
                    files.append(file_info)
                    logger.info(f"✅ Added CSV file: {key} ({obj['Size']} bytes)")
                else:
                    logger.info(f"⏭️  Skipped non-CSV file: {key}")
        else:
            logger.info("No objects found in bucket")

        # Sort by last modified date (newest first)
        logger.info(f"Sorting {len(files)} CSV files by last modified date")
        files.sort(key=lambda x: x["last_modified"], reverse=True)

        result = {"success": True, "files": files}

        logger.info("=" * 50)
        logger.info("✅ LIST_FILES TOOL COMPLETED SUCCESSFULLY")
        logger.info(f"Found {len(files)} CSV files")
        logger.info("=" * 50)

        return {"body": result}

    except Exception as e:
        error_msg = str(e)
        logger.error("=" * 50)
        logger.error("❌ LIST_FILES TOOL FAILED")
        logger.error(f"Error: {error_msg}")
        logger.error("=" * 50)
        return {"body": {"success": False, "error": error_msg}}
