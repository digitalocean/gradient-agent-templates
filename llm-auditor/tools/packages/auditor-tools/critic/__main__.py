import requests
from typing import Dict, Any
import os


AGENT_ENDPOINT = os.getenv("CRITIC_AGENT_ENDPOINT")
AGENT_ACCESS_KEY = os.getenv("CRITIC_AGENT_ACCESS_KEY")

API_URL = f"{AGENT_ENDPOINT}/api/v1/chat/completions"


def get_response(query: str) -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AGENT_ACCESS_KEY}",
    }
    payload = {
        "messages": [{"role": "user", "content": query}],
        "stream": False,
        "include_functions_info": False,
        "include_retrieval_info": False,
        "include_guardrails_info": False,
    }

    response = requests.post(API_URL, headers=headers, json=payload)
    response.raise_for_status()

    choices = response.json().get("choices", [])
    if choices:
        response_string = choices[0].get("message", {}).get("content", "")
    else:
        response_string = "The agent did not respond"

    return response_string


def main(args: Dict[str, Any]):
    query = args.get("query")
    agent_response = get_response(query)
    return {"body": {"assessment": agent_response}}
