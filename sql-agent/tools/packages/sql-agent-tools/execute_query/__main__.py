from typing import Dict, Any, Optional, List
import os
import mysql.connector
from mysql.connector import Error
import re
import decimal
import json
import datetime


def _make_json_safe(obj):
    if isinstance(obj, list):
        return [_make_json_safe(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, decimal.Decimal):
        return float(obj)  # or str(obj) if you care about precision
    elif isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    else:
        return obj


class QueryExecutionResult:
    """Class to standardize query execution results"""

    def __init__(
        self,
        success: bool,
        data: Optional[List[Dict]] = None,
        error: Optional[str] = None,
        query: Optional[str] = None,
        execution_time: Optional[float] = None,
        row_count: Optional[int] = None,
    ):
        self.success = success
        self.data = data or []
        self.error = error
        self.query = query
        self.execution_time = execution_time
        self.row_count = row_count or len(self.data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary format"""
        return {
            "success": self.success,
            "data": json.dumps(_make_json_safe(self.data), indent=2),
            "error": self.error,
        }


def validate_select_query(query: str) -> bool:
    """
    Validates that the query is a safe SELECT statement.

    Args:
        query: SQL query string to validate

    Returns:
        bool: True if query is safe, False otherwise
    """

    # Remove comments and normalize whitespace
    query_clean = re.sub(r"--.*?\n", "", query, flags=re.MULTILINE)
    query_clean = re.sub(r"/\*.*?\*/", "", query_clean, flags=re.DOTALL)
    query_clean = " ".join(query_clean.split()).strip().upper()

    # Check if query starts with SELECT
    if not query_clean.startswith("SELECT"):
        return False

    # List of dangerous keywords that should not be in read-only queries
    dangerous_keywords = [
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "CREATE",
        "ALTER",
        "TRUNCATE",
        "REPLACE",
        "MERGE",
        "CALL",
        "EXEC",
        "EXECUTE",
        "LOAD",
        "OUTFILE",
        "DUMPFILE",
        "INTO OUTFILE",
        "INTO DUMPFILE",
    ]

    for keyword in dangerous_keywords:
        if keyword in query_clean:
            return False

    return True


def execute_select_query(
    connection, query: str, params: Optional[List] = None
) -> QueryExecutionResult:
    """
    Executes a SELECT query safely and returns structured results.

    Args:
        connection: Active MySQL database connection
        query: SQL SELECT query to execute
        params: Optional parameters for parameterized queries

    Returns:
        QueryExecutionResult: Structured result object
    """

    import time

    # Validate query safety
    if not validate_select_query(query):
        return QueryExecutionResult(
            success=False,
            error="Query validation failed: Only SELECT statements are allowed",
            query=query,
        )

    cursor = None
    start_time = time.time()

    try:
        cursor = connection.cursor(dictionary=True)

        # Execute query with or without parameters
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        # Fetch results
        results = cursor.fetchall()
        execution_time = time.time() - start_time

        return QueryExecutionResult(
            success=True,
            data=results,
            query=query,
            execution_time=execution_time,
            row_count=len(results),
        )

    except Error as e:
        execution_time = time.time() - start_time
        return QueryExecutionResult(
            success=False,
            error=f"MySQL Error: {e}",
            query=query,
            execution_time=execution_time,
        )
    except Exception as e:
        execution_time = time.time() - start_time
        return QueryExecutionResult(
            success=False,
            error=f"Unexpected error: {e}",
            query=query,
            execution_time=execution_time,
        )
    finally:
        if cursor:
            cursor.close()


def format_query_results(result: QueryExecutionResult, max_rows: int = 100) -> str:
    """
    Formats query results in a human-readable format.

    Args:
        result: QueryExecutionResult object
        max_rows: Maximum number of rows to display

    Returns:
        Formatted string representation of results
    """

    if not result.success:
        return f"Query failed: {result.error}"

    if not result.data:
        return "Query executed successfully but returned no results."

    output = []
    output.append(
        f"Query Results ({result.row_count} rows, {result.execution_time:.3f}s):"
    )
    output.append("=" * 60)

    # Display column headers
    if result.data:
        headers = list(result.data[0].keys())
        header_row = " | ".join(f"{h:15}" for h in headers)
        output.append(header_row)
        output.append("-" * len(header_row))

        # Display data rows (limited by max_rows)
        display_rows = result.data[:max_rows]
        for row in display_rows:
            row_str = " | ".join(f"{str(row.get(h, 'NULL')):15}" for h in headers)
            output.append(row_str)

        if len(result.data) > max_rows:
            output.append(f"... and {len(result.data) - max_rows} more rows")

    return "\n".join(output)


def execute_query_with_error_handling(
    connection, query: str, max_rows: int = 100
) -> Dict[str, Any]:
    """
    High-level function to execute query with comprehensive error handling.

    Args:
        connection: Database connection
        query: SQL query to execute
        max_rows: Maximum rows to return

    Returns:
        Dictionary with execution results and metadata
    """

    result = execute_select_query(connection, query)

    # Limit results if needed
    if result.success and len(result.data) > max_rows:
        result.data = result.data[:max_rows]
        result.row_count = max_rows
        if not result.error:
            result.error = f"Results limited to {max_rows} rows"

    return result.to_dict()


class DatabaseToolManager:
    """
    Manages database connections
    """

    def __init__(self):
        self.connection = None
        self.connection_config = self._load_connection_config()

    def _load_connection_config(self) -> Dict[str, Any]:
        """Load database connection configuration from environment variables"""
        return {
            "host": os.getenv("DB_HOST"),
            "user": os.getenv("DB_AGENT_USER"),
            "password": os.getenv("DB_AGENT_PASSWORD"),
            "port": int(os.getenv("DB_PORT")),
            "database": os.getenv("DB_NAME"),
            "autocommit": True,
            "raise_on_warnings": True,
        }

    def connect(self) -> bool:
        """
        Establish connection to the database.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            if self.connection and self.connection.is_connected():
                return True

            self.connection = mysql.connector.connect(**self.connection_config)
            print(f"Connected to database: {self.connection_config['database']}")
            return True

        except Error as e:
            print(f"Error connecting to database: {e}")
            return False

    def disconnect(self):
        """Close the database connection"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            print("Database connection closed")

    def is_connected(self) -> bool:
        """Check if database connection is active"""
        return self.connection and self.connection.is_connected()

    def execute_query(self, query: str, max_rows: int = 100) -> Dict[str, Any]:
        """
        Tool method: Execute a SELECT query and return results.

        Args:
            query: SQL SELECT query to execute
            max_rows: Maximum number of rows to return

        Returns:
            Dict containing query results and metadata
        """
        if not self.is_connected():
            if not self.connect():
                return {
                    "success": False,
                    "error": "Unable to connect to database",
                    "data": [],
                }

        try:
            result = execute_query_with_error_handling(
                self.connection, query, max_rows=max_rows
            )
            self.disconnect()
            return result
        except Exception as e:
            self.disconnect()
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "data": "[]",
            }


def main(args):
    db_tool_manager = DatabaseToolManager()
    query_string = args.get("query")
    if query_string is None:
        return {
            "body": {
                "success": False,
                "error": f"No query was provided. A query must be provided.",
                "data": "[]",
            }
        }
    query_result = db_tool_manager.execute_query(query=query_string, max_rows=100)
    return {"body": query_result}
