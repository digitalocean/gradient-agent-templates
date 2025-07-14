# This function is used by the critic agent to search the web to verify factual information.

import os
import requests
from typing import Any, Dict

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
API_URL = "https://api.tavily.com/search"

# Since searches can be dynamic, this variable is used to set a cap on the number of maximum characters allowed in the results
# This is to prevent the search context from being very large and crossing the input token limit of the agent in rare circumstances
# As a rough estimatem, 1 token ~= 4 English characters, so this restricts the search results to roughly 3K tokens.
CHARACTER_LIMIT = 12000


def search(query: str) -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TAVILY_API_KEY}",
    }
    data = {"query": query}

    response = requests.post(API_URL, headers=headers, json=data)
    response.raise_for_status()
    response_dict = response.json()
    sources = response_dict.get("results", [])
    context = [
        {"url": source["url"], "content": source["content"]} for source in sources
    ]
    # Combine into one string
    context_string = "\n\n".join(
        f"Url: {item['url']}\nContext: {item['content']}" for item in context
    )
    return context_string[: min(len(context_string), CHARACTER_LIMIT)]


def main(args: Dict[str, Any]):
    query = args.get("query")
    search_context = search(query)
    return {"body": {"context": search_context}}
