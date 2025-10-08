import pandas as pd
import boto3
import os
import io
import logging
from typing import Dict, Any
import sys
from io import StringIO

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute pandas code on the loaded CSV data.

    Args:
        args: Dictionary containing 'filename' and 'pandas_code' parameters

    Returns:
        Dictionary with the result of the code execution
    """
    logger.info("=" * 50)
    logger.info("🐍 EXECUTE_PANDAS_CODE TOOL CALLED")
    logger.info("=" * 50)
    logger.info(f"Input args: {args}")

    try:
        filename = args.get("filename")
        pandas_code = args.get("pandas_code")

        logger.info(f"Filename: {filename}")
        logger.info(
            f"Pandas code length: {len(pandas_code) if pandas_code else 0} characters"
        )
        logger.info(
            f"Pandas code preview: {pandas_code[:200] if pandas_code else 'None'}..."
        )

        if not filename or not pandas_code:
            error_msg = "Filename and pandas_code are required"
            logger.error(f"❌ {error_msg}")
            return {"body": {"success": False, "error": error_msg}}

        # Clean up the pandas code to handle escaping issues
        # Replace any escaped quotes with proper quotes
        logger.info("Cleaning up pandas code...")
        original_code = pandas_code
        pandas_code = pandas_code.replace('\\"', '"').replace("\\'", "'")
        if original_code != pandas_code:
            logger.info("Code was cleaned (escaped quotes replaced)")

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
        logger.info(f"DataFrame columns: {list(df.columns)}")

        # Capture stdout to get print statements
        logger.info("Setting up stdout capture for code execution...")
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            # Execute the pandas code
            logger.info("Executing pandas code...")
            logger.info(f"Code to execute:\n{pandas_code}")

            # The code should use 'df' as the DataFrame variable name
            local_vars = {"df": df, "pd": pd, "np": __import__("numpy")}
            logger.info("Local variables prepared: df, pd, np")

            # Add some safety restrictions
            safe_builtins = {
                "len": len,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "list": list,
                "dict": dict,
                "tuple": tuple,
                "set": set,
                "min": min,
                "max": max,
                "sum": sum,
                "abs": abs,
                "round": round,
                "print": print,
                "type": type,
                "isinstance": isinstance,
            }
            logger.info("Safe builtins configured for code execution")

            exec(pandas_code, {"__builtins__": safe_builtins}, local_vars)
            logger.info("✅ Code executed successfully")

            # Get the captured output
            output = captured_output.getvalue()
            logger.info(f"Captured output length: {len(output)} characters")

            # If no output was captured, try to get the result from the last expression
            if not output.strip():
                logger.info("No output captured, trying to evaluate last line...")
                # Try to evaluate the last line as an expression
                lines = pandas_code.strip().split("\n")
                last_line = lines[-1].strip()
                logger.info(f"Last line to evaluate: {last_line}")

                if last_line and not last_line.startswith("#"):
                    try:
                        result = eval(
                            last_line, {"__builtins__": safe_builtins}, local_vars
                        )
                        logger.info(
                            f"Last line evaluation successful, result type: {type(result)}"
                        )

                        if result is not None:
                            if isinstance(result, pd.DataFrame):
                                output = f"DataFrame shape: {result.shape}\nColumns: {list(result.columns)}\nFirst 5 rows:\n{result.head().to_string()}"
                                logger.info(
                                    f"Result is DataFrame with shape: {result.shape}"
                                )
                            elif isinstance(result, pd.Series):
                                output = f"Series length: {len(result)}\nFirst 10 values:\n{result.head(10).to_string()}"
                                logger.info(
                                    f"Result is Series with length: {len(result)}"
                                )
                            else:
                                output = str(result)
                                logger.info(
                                    f"Result is {type(result)}: {str(result)[:100]}..."
                                )
                    except Exception as eval_error:
                        output = f"Code executed successfully (no output captured). Last line evaluation failed: {str(eval_error)}"
                        logger.warning(
                            f"Last line evaluation failed: {str(eval_error)}"
                        )
            else:
                logger.info(f"Output captured from print statements: {output[:200]}...")

            result = {"success": True, "result": output}

            logger.info("=" * 50)
            logger.info("✅ EXECUTE_PANDAS_CODE TOOL COMPLETED SUCCESSFULLY")
            logger.info(f"Result length: {len(output)} characters")
            logger.info("=" * 50)

            return {"body": result}

        except Exception as e:
            error_msg = f"Code execution error: {str(e)}"
            logger.error("=" * 50)
            logger.error("❌ CODE EXECUTION FAILED")
            logger.error(f"Error: {error_msg}")
            logger.error("=" * 50)
            return {"body": {"success": False, "error": error_msg}}
        finally:
            # Restore stdout
            logger.info("Restoring stdout...")
            sys.stdout = old_stdout

    except Exception as e:
        error_msg = str(e)
        logger.error("=" * 50)
        logger.error("❌ EXECUTE_PANDAS_CODE TOOL FAILED")
        logger.error(f"Error: {error_msg}")
        logger.error("=" * 50)
        return {"body": {"success": False, "error": error_msg}}
