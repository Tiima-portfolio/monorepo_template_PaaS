#!/usr/bin/env python3
from __PKG__ import greeting


def test_greets_by_name():
    assert greeting("Ada") == "Hello from __NAME__, Ada"
