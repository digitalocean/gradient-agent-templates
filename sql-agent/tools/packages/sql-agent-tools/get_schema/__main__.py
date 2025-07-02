from typing import Dict, Any
import os
import mysql.connector
from mysql.connector import Error


def get_database_schema(connection) -> Dict[str, Any]:
    """
    Retrieves comprehensive schema information from the database.

    Args:
        connection: Active MySQL database connection

    Returns:
        Dict containing complete schema information including:
        - database_name: Name of the database
        - tables: List of table information with columns, indexes, and constraints
        - relationships: Foreign key relationships between tables
    """

    try:
        cursor = connection.cursor(dictionary=True)

        # Get current database name
        cursor.execute("SELECT DATABASE() as db_name")
        db_result = cursor.fetchone()
        database_name = db_result["db_name"] if db_result else "unknown"

        schema_info = {
            "database_name": database_name,
            "tables": [],
            "relationships": [],
        }

        # Get all tables in the database
        cursor.execute(
            """
            SELECT TABLE_NAME, TABLE_TYPE, ENGINE, TABLE_COMMENT
            FROM information_schema.TABLES 
            WHERE TABLE_SCHEMA = %s
            ORDER BY TABLE_NAME
        """,
            (database_name,),
        )

        tables = cursor.fetchall()

        for table in tables:
            table_name = table["TABLE_NAME"]

            # Get columns for this table
            cursor.execute(
                """
                SELECT 
                    COLUMN_NAME,
                    DATA_TYPE,
                    IS_NULLABLE,
                    COLUMN_DEFAULT,
                    COLUMN_KEY,
                    EXTRA,
                    COLUMN_COMMENT,
                    CHARACTER_MAXIMUM_LENGTH,
                    NUMERIC_PRECISION,
                    NUMERIC_SCALE,
                    COLUMN_TYPE
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                ORDER BY ORDINAL_POSITION
            """,
                (database_name, table_name),
            )

            columns = cursor.fetchall()

            # Get indexes for this table
            cursor.execute(
                """
                SELECT 
                    INDEX_NAME,
                    COLUMN_NAME,
                    NON_UNIQUE,
                    INDEX_TYPE
                FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                ORDER BY INDEX_NAME, SEQ_IN_INDEX
            """,
                (database_name, table_name),
            )

            indexes = cursor.fetchall()

            # Process indexes into a more readable format
            index_dict = {}
            for idx in indexes:
                idx_name = idx["INDEX_NAME"]
                if idx_name not in index_dict:
                    index_dict[idx_name] = {
                        "name": idx_name,
                        "unique": not idx["NON_UNIQUE"],
                        "type": idx["INDEX_TYPE"],
                        "columns": [],
                    }
                index_dict[idx_name]["columns"].append(idx["COLUMN_NAME"])

            table_info = {
                "name": table_name,
                "type": table["TABLE_TYPE"],
                "engine": table["ENGINE"],
                "comment": table["TABLE_COMMENT"],
                "columns": columns,
                "indexes": list(index_dict.values()),
            }

            schema_info["tables"].append(table_info)

        # Get foreign key relationships
        cursor.execute(
            """
            SELECT 
                TABLE_NAME,
                COLUMN_NAME,
                CONSTRAINT_NAME,
                REFERENCED_TABLE_NAME,
                REFERENCED_COLUMN_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = %s 
                AND REFERENCED_TABLE_NAME IS NOT NULL
            ORDER BY TABLE_NAME, COLUMN_NAME
        """,
            (database_name,),
        )

        relationships = cursor.fetchall()
        schema_info["relationships"] = relationships

        # Get table row counts for additional context
        for table_info in schema_info["tables"]:
            table_name = table_info["name"]
            try:
                cursor.execute(f"SELECT COUNT(*) as row_count FROM `{table_name}`")
                count_result = cursor.fetchone()
                table_info["row_count"] = (
                    count_result["row_count"] if count_result else 0
                )
            except Error:
                table_info["row_count"] = "unknown"

        return schema_info

    except Error as e:
        raise Exception(f"Error retrieving database schema: {e}")
    finally:
        if cursor:
            cursor.close()


def format_schema_for_llm(schema_info: Dict[str, Any]) -> str:
    """
    Formats schema information in a readable format for LLM consumption.

    Args:
        schema_info: Schema dictionary from get_database_schema()

    Returns:
        Formatted string representation of the schema
    """

    output = []
    output.append(f"Database: {schema_info['database_name']}")
    output.append("=" * 50)

    # Tables section
    for table in schema_info["tables"]:
        output.append(f"\nTable: {table['name']} ({table['row_count']} rows)")
        output.append("-" * 40)

        if table["comment"]:
            output.append(f"Description: {table['comment']}")

        output.append("Columns:")
        for col in table["columns"]:
            null_info = "NULL" if col["IS_NULLABLE"] == "YES" else "NOT NULL"
            default_info = (
                f", DEFAULT: {col['COLUMN_DEFAULT']}" if col["COLUMN_DEFAULT"] else ""
            )
            key_info = f" [{col['COLUMN_KEY']}]" if col["COLUMN_KEY"] else ""
            extra_info = f" {col['EXTRA']}" if col["EXTRA"] else ""

            output.append(
                f"  - {col['COLUMN_NAME']}: {col['COLUMN_TYPE']} {null_info}{default_info}{key_info}{extra_info}"
            )

            if col["COLUMN_COMMENT"]:
                output.append(f"    Comment: {col['COLUMN_COMMENT']}")

        if table["indexes"]:
            output.append("Indexes:")
            for idx in table["indexes"]:
                unique_info = "UNIQUE " if idx["unique"] else ""
                output.append(
                    f"  - {unique_info}{idx['name']} ({', '.join(idx['columns'])})"
                )

    # Relationships section
    if schema_info["relationships"]:
        output.append("\nForeign Key Relationships:")
        output.append("-" * 40)
        for rel in schema_info["relationships"]:
            output.append(
                f"  - {rel['TABLE_NAME']}.{rel['COLUMN_NAME']} -> {rel['REFERENCED_TABLE_NAME']}.{rel['REFERENCED_COLUMN_NAME']}"
            )

    return "\n".join(output)


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

    def get_schema(self) -> Dict[str, Any]:
        """
        Tool method: Retrieve database schema information.

        Returns:
            Dict containing complete schema information
        """
        if not self.is_connected():
            if not self.connect():
                return {
                    "success": False,
                    "error": "Unable to connect to database",
                    "formatted_schema": None,
                }

        try:
            schema_info = get_database_schema(self.connection)
            self.disconnect()
            return {
                "success": True,
                "error": None,
                "formatted_schema": format_schema_for_llm(schema_info),
            }
        except Exception as e:
            self.disconnect()
            return {"success": False, "error": str(e), "formatted_schema": None}


def main(args):
    db_tool_manager = DatabaseToolManager()
    schema = db_tool_manager.get_schema()
    return {"body": schema}
