#!/usr/bin/env python3
"""Consumer contract: what the simulator sends must exist in orders' published
OpenAPI contract (product/services/orders/api/openapi.yaml)."""

from pathlib import Path

import yaml

from order_simulator.requests import greeting_request

CONTRACT = (
    Path(__file__).resolve().parents[5] / "product/services/orders/api/openapi.yaml"
)


def test_greeting_request_matches_the_orders_contract():
    spec = yaml.safe_load(CONTRACT.read_text())
    request = greeting_request("Ada")
    operation = spec["paths"][request["path"]][request["method"]]
    declared = {p["name"] for p in operation["parameters"] if p["in"] == "query"}
    required = {
        p["name"]
        for p in operation["parameters"]
        if p["in"] == "query" and p.get("required")
    }
    assert set(request["query"]) <= declared
    assert required <= set(request["query"])
