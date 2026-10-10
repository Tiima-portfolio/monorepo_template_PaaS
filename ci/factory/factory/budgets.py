#!/usr/bin/env python3
"""Time budget evidence: how long this PR's feedback took against its tier's
budget. Hard limits are enforced as job and step timeouts in the workflow."""

from datetime import datetime

from .numbers import round1


def parse_time(value) -> datetime:
    return value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def feedback_budget(tier, started_at, now, policy) -> dict:
    limits = policy["feedback"][tier]
    minutes = round1((parse_time(now) - parse_time(started_at)).total_seconds() / 60)
    return {"minutes": minutes, **limits, "ok": minutes <= limits["budget"]}
