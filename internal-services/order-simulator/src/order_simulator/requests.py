"""Requests the simulator sends to the orders service."""

GREETING_PATH = "/greeting"


def greeting_request(name: str) -> dict:
    """The request for orders' greeting endpoint."""
    return {"method": "get", "path": GREETING_PATH, "query": {"name": name}}
