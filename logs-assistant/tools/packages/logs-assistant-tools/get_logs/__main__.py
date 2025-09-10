import os
import requests
import re
from datetime import datetime, timezone

MAX_BLOCK_COUNT = 10


def get_current_timestamp():
    # Current UTC timestamp
    utc_now = datetime.now(timezone.utc)
    return f"The current time is: {utc_now.isoformat()}\n---\n"


def get_digitalocean_app_logs(app_id: str, log_type: str):
    """
    Fetch logs for a DigitalOcean app with a specific log type.

    :param app_id: The ID of your DigitalOcean app.
    :param token: Your DigitalOcean API token.
    :param log_type: Type of logs to fetch (e.g., "build", "deploy", "run").
    :return: JSON response containing logs.
    """
    url = f"https://api.digitalocean.com/v2/apps/{app_id}/logs"
    token = os.getenv("AGENT_TOKEN")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    params = {"type": log_type}

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        return response.json()
    elif response.status_code == 400:
        return response.json()
    else:
        raise Exception(f"Error {response.status_code}: {response.text}")


def create_log_set(application_id):
    log_set = get_current_timestamp()
    log_set += "\nBuildtime Errors:\n" + get_error_logs_for_application(
        application_id, "BUILD"
    )
    log_set += "\nDeploytime Errors:\n" + get_error_logs_for_application(
        application_id, "DEPLOY"
    )
    log_set += "\nRuntime Errors:\n" + get_error_logs_for_application(
        application_id, "RUN"
    )
    return log_set


def get_runtime_error_logs(application_id: str):
    return get_error_logs_for_application(application_id, "RUN")


def get_buildtime_error_logs(application_id: str):
    return get_error_logs_for_application(application_id, "BUILD")


def get_deploytime_error_logs(application_id: str):
    return get_error_logs_for_application(application_id, "DEPLOY")


def get_error_logs_for_application(application_id: str, log_type: str):
    try:
        logs_resp = get_digitalocean_app_logs(app_id=application_id, log_type=log_type)
        url = logs_resp.get("url")
        if url is None:
            historic_urls = logs_resp.get("historic_urls")
            if not historic_urls:
                message = logs_resp.get("message")
                if message:
                    return message
                return "No logs URL or historic log URL could be obtained. No logs were found."
            url = historic_urls[0]
        response = requests.get(url)
        response.raise_for_status()
        lines = response.text.splitlines()

        # Pattern to detect the start of a log entry by log level
        entry_start_pattern = re.compile(
            r"^\S+\s+\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+(INFO|ERROR|WARNING):"
        )

        blocks = []
        current_block = []
        capturing = False

        for line in lines:
            is_entry_start = bool(entry_start_pattern.match(line))
            is_error_or_warning = "ERROR" in line or "WARNING" in line

            if is_error_or_warning and is_entry_start:
                # Start a new block
                if current_block:
                    blocks.append("\n".join(current_block))
                    current_block = []
                capturing = True

            if capturing:
                if is_entry_start and not is_error_or_warning and current_block:
                    # A new entry that's NOT error/warning means end of this block
                    blocks.append("\n".join(current_block))
                    current_block = []
                    capturing = False

            if capturing:
                current_block.append(line)

        # Add last block if any
        if current_block:
            blocks.append("\n".join(current_block))
        # Get last set of blocks
        blocks = blocks[-MAX_BLOCK_COUNT:]
        error_string = ""
        for block in blocks:
            error_string += "-" * 40 + "\n" + block + "\n" + "-" * 40
        if not len(error_string):
            error_string = "No errors or warnings were found!"
        return error_string
    except Exception as e:
        print(e)
        return "An error occurred while fetching the logs."


def create_response(logs_str: str):
    return {"result": logs_str}


def main(args):
    app_id = args.get("app_id")
    if app_id is None:
        return {"body": create_response("Please provide a valid App ID")}
    return {"body": create_response(create_log_set(app_id))}
