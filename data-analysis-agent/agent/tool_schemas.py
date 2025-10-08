"""
Tool schemas for the Data Analysis Agent template - pydo format for Gradient SDK
"""

# List Files Tool
LIST_FILES_TOOL_DESCRIPTION = (
    "List all CSV files available in the Spaces bucket with their metadata."
)

LIST_FILES_INPUT_SCHEMA = {"parameters": []}

LIST_FILES_OUTPUT_SCHEMA = {
    "properties": [
        {
            "name": "success",
            "type": "boolean",
            "description": "Whether the file listing was successful",
        },
        {
            "name": "files",
            "type": "array",
            "description": "List of CSV files with metadata",
        },
        {"name": "error", "type": "string", "description": "Error message if failed"},
    ]
}

# Load CSV Tool
LOAD_CSV_TOOL_DESCRIPTION = (
    "Load a CSV file from the Spaces bucket into memory as a pandas DataFrame. "
    "Returns column headers, data types, and basic info. Use this before performing any analysis."
)

LOAD_CSV_INPUT_SCHEMA = {
    "parameters": [
        {
            "in": "query",
            "name": "filename",
            "schema": {"type": "string"},
            "required": True,
            "description": "Name of the CSV file to load from the bucket",
        },
        {
            "in": "query",
            "name": "max_rows",
            "schema": {"type": "integer"},
            "required": False,
            "description": "Maximum number of rows to load (optional, no limit by default)",
        },
    ]
}

LOAD_CSV_OUTPUT_SCHEMA = {
    "properties": [
        {
            "name": "success",
            "type": "boolean",
            "description": "Whether the CSV loading was successful",
        },
        {"name": "columns", "type": "array", "description": "List of column names"},
        {
            "name": "dtypes",
            "type": "object",
            "description": "Data types for each column",
        },
        {
            "name": "shape",
            "type": "array",
            "description": "DataFrame shape [rows, columns]",
        },
        {"name": "sample_data", "type": "array", "description": "First 5 rows of data"},
        {"name": "error", "type": "string", "description": "Error message if failed"},
    ]
}

# Get Column Info Tool
GET_COLUMN_INFO_TOOL_DESCRIPTION = (
    "Get detailed information about a specific column in the loaded CSV data."
)

GET_COLUMN_INFO_INPUT_SCHEMA = {
    "parameters": [
        {
            "in": "query",
            "name": "filename",
            "schema": {"type": "string"},
            "required": True,
            "description": "Name of the CSV file",
        },
        {
            "in": "query",
            "name": "column_name",
            "schema": {"type": "string"},
            "required": True,
            "description": "Name of the column to analyze",
        },
    ]
}

GET_COLUMN_INFO_OUTPUT_SCHEMA = {
    "properties": [
        {
            "name": "success",
            "type": "boolean",
            "description": "Whether the operation was successful",
        },
        {
            "name": "column_info",
            "type": "object",
            "description": "Column information including data type, unique values, null count",
        },
        {"name": "error", "type": "string", "description": "Error message if failed"},
    ]
}


# Execute Pandas Code Tool
EXECUTE_PANDAS_CODE_TOOL_DESCRIPTION = (
    "Execute pandas code on the loaded CSV data. Use this for complex queries and analysis. "
    "The code will be executed on the actual data in memory."
)

EXECUTE_PANDAS_CODE_INPUT_SCHEMA = {
    "parameters": [
        {
            "in": "query",
            "name": "filename",
            "schema": {"type": "string"},
            "required": True,
            "description": "Name of the CSV file",
        },
        {
            "in": "query",
            "name": "pandas_code",
            "schema": {"type": "string"},
            "required": True,
            "description": "Pandas code to execute. Use 'df' as the variable name for the DataFrame.",
        },
    ]
}

EXECUTE_PANDAS_CODE_OUTPUT_SCHEMA = {
    "properties": [
        {
            "name": "success",
            "type": "boolean",
            "description": "Whether the code execution was successful",
        },
        {
            "name": "result",
            "type": "string",
            "description": "Result of the pandas code execution",
        },
        {"name": "error", "type": "string", "description": "Error message if failed"},
    ]
}
