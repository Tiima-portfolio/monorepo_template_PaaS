#!/usr/bin/env python3
from pricing import greeting


def test_greets_by_name():
    assert greeting("Ada") == "Hello from pricing, Ada"
