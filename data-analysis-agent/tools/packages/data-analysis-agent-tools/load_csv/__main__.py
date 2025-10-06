import json
import pandas as pd
import boto3
import os
import io
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Load a CSV file from DigitalOcean Spaces bucket into memory as a pandas DataFrame.

    Args:
        args: Dictionary containing 'filename' and optional 'max_rows' parameters

    Returns:
        Dictionary with success status, column info, and sample data
    """
    logger.info("=" * 50)
    logger.info("📁 LOAD_CSV TOOL CALLED")
    logger.info("=" * 50)
    logger.info(f"Input args: {args}")

    try:
        filename = args.get("filename")
        max_rows = args.get("max_rows", None)  # No default limit

        logger.info(f"Filename: {filename}")
        logger.info(f"Max rows: {max_rows}")

        if not filename:
            error_msg = "Filename is required"
            logger.error(f"❌ {error_msg}")
            return {"body": {"success": False, "error": error_msg}}

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

        # Download CSV file
        logger.info(f"Downloading CSV file: {filename}")
        response = s3_client.get_object(Bucket=bucket_name, Key=filename)
        csv_content = response["Body"].read().decode("utf-8")
        logger.info(f"Downloaded {len(csv_content)} characters from {filename}")

        # Load into pandas DataFrame
        logger.info("Loading CSV content into pandas DataFrame...")
        df = pd.read_csv(io.StringIO(csv_content))
        logger.info(f"DataFrame created with shape: {df.shape}")

        # Limit rows if specified (only if max_rows is provided)
        if max_rows is not None and len(df) > max_rows:
            logger.info(f"Limiting DataFrame to {max_rows} rows (was {len(df)})")
            df = df.head(max_rows)
            logger.info(f"DataFrame shape after limiting: {df.shape}")

        # Get basic info
        logger.info("Extracting DataFrame information...")
        columns = df.columns.tolist()
        dtypes = df.dtypes.astype(str).to_dict()
        shape = list(df.shape)
        sample_data = df.head(5).to_dict("records")

        logger.info(f"Columns: {columns}")
        logger.info(f"Data types: {dtypes}")
        logger.info(f"Shape: {shape}")
        logger.info(f"Sample data rows: {len(sample_data)}")

        result = {
            "success": True,
            "columns": columns,
            "dtypes": dtypes,
            "shape": shape,
            "sample_data": sample_data,
        }

        logger.info("=" * 50)
        logger.info("✅ LOAD_CSV TOOL COMPLETED SUCCESSFULLY")
        logger.info(f"Loaded {shape[0]} rows, {shape[1]} columns")
        logger.info("=" * 50)

        return {"body": result}

    except Exception as e:
        error_msg = str(e)
        logger.error("=" * 50)
        logger.error("❌ LOAD_CSV TOOL FAILED")
        logger.error(f"Error: {error_msg}")
        logger.error("=" * 50)
        return {"body": {"success": False, "error": error_msg}}
