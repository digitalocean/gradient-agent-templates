import os
import requests
from typing import Any, Dict

TWILIO_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER")

API_URL = (
    f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json"
    if TWILIO_SID
    else None
)


def send_message(to_number: str, from_number: str, message_text: str):
    if not to_number or not message_text:
        return {"statusCode": 400, "body": "Both 'to' and 'body' fields are required."}

    data = {"To": to_number, "From": from_number, "Body": message_text}

    response = requests.post(API_URL, data=data, auth=(TWILIO_SID, TWILIO_TOKEN))
    response.raise_for_status()
    return response.json()


def main(args: Dict[str, Any]):
    to_number = args.get("to_number")
    message_text = args.get("message_text")

    if not to_number or not message_text:
        return {
            "statusCode": 400,
            "body": "Both 'to_number' and 'message_text' fields are required.",
        }

    message_response = send_message(
        to_number=to_number, from_number=FROM_NUMBER, message_text=message_text
    )
    return {
        "body": {
            "sid": message_response.get("sid"),
            "status": message_response.get("status"),
            "to": message_response.get("to"),
        }
    }
