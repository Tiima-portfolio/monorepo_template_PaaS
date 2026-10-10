#!/usr/bin/env python3
"""Writes the API's schema to openapi.json, the contract radiator-web reads:
python -m radiator_api.openapi > openapi.json"""

import json

from . import app


def schema() -> str:
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    print(schema(), end="")
