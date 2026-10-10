#!/usr/bin/env python3
from order_simulator import greeting


def test_greets_by_name():
    assert greeting("Ada") == "Hello from order-simulator, Ada"
