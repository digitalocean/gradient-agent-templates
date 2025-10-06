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
    Get detailed information about a specific column in the loaded CSV data.

    Args:
        args: Dictionary containing 'filename' and 'column_name' parameters

    Returns:
        Dictionary with column information
    """
    logger.info("=" * 50)
    logger.info("📊 GET_COLUMN_INFO TOOL CALLED")
    logger.info("=" * 50)
    logger.info(f"Input args: {args}")

    try:
        filename = args.get("filename")
        column_name = args.get("column_name")

        logger.info(f"Filename: {filename}")
        logger.info(f"Column name: {column_name}")

        if not filename or not column_name:
            error_msg = "Filename and column_name are required"
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
        logger.info(f"Available columns: {list(df.columns)}")

        # Check if column exists
        if column_name not in df.columns:
            error_msg = f"Column '{column_name}' not found in CSV"
            logger.error(f"❌ {error_msg}")
            logger.error(f"Available columns: {list(df.columns)}")
            return {"body": {"success": False, "error": error_msg}}

        logger.info(f"✅ Column '{column_name}' found in DataFrame")

        # Get column information
        logger.info(f"Analyzing column: {column_name}")
        column_series = df[column_name]

        logger.info("Calculating basic column statistics...")
        column_info = {
            "name": column_name,
            "dtype": str(column_series.dtype),
            "count": int(column_series.count()),
            "null_count": int(column_series.isnull().sum()),
            "null_percentage": float(
                column_series.isnull().sum() / len(column_series) * 100
            ),
            "unique_count": int(column_series.nunique()),
            "unique_percentage": float(
                column_series.nunique() / len(column_series) * 100
            ),
        }

        logger.info(
            f"Basic stats - Count: {column_info['count']}, Nulls: {column_info['null_count']}, Unique: {column_info['unique_count']}"
        )

        # Add type-specific information
        if pd.api.types.is_numeric_dtype(column_series):
            logger.info("Column is numeric, calculating statistical measures...")
            column_info.update(
                {
                    "min": float(column_series.min())
                    if not column_series.empty
                    else None,
                    "max": float(column_series.max())
                    if not column_series.empty
                    else None,
                    "mean": float(column_series.mean())
                    if not column_series.empty
                    else None,
                    "std": float(column_series.std())
                    if not column_series.empty
                    else None,
                }
            )
            logger.info(
                f"Numeric stats - Min: {column_info['min']}, Max: {column_info['max']}, Mean: {column_info['mean']}"
            )
        else:
            logger.info("Column is non-numeric, calculating value counts...")
            # For non-numeric columns, get value counts
            value_counts = column_series.value_counts().head(10)
            column_info["top_values"] = value_counts.to_dict()
            logger.info(f"Top values: {dict(list(value_counts.head(5).items()))}")

        result = {"success": True, "column_info": column_info}

        logger.info("=" * 50)
        logger.info("✅ GET_COLUMN_INFO TOOL COMPLETED SUCCESSFULLY")
        logger.info(f"Analyzed column: {column_name}")
        logger.info("=" * 50)

        return {"body": result}

    except Exception as e:
        error_msg = str(e)
        logger.error("=" * 50)
        logger.error("❌ GET_COLUMN_INFO TOOL FAILED")
        logger.error(f"Error: {error_msg}")
        logger.error("=" * 50)
        return {"body": {"success": False, "error": error_msg}}
