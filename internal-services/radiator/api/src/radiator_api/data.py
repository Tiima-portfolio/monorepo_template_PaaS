#!/usr/bin/env python3
"""Mock factory data. It changes once a minute, so the radiator looks alive,
and is the same for every request within that minute."""

import random
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel

# The services in this monorepo and their owners, from their service.yaml.
SERVICES = {
    "catalog": "team-catalog",
    "orders": "team-orders",
    "pricing": "team-pricing",
    "inventory": "team-inventory",
    "edge-proxy": "team-platform",
    "order-simulator": "team-orders",
    "buildkit": "team-platform",
}
PRIORITIES = ("P0", "P1", "P2", "P3", "P4")

Status = Literal["passing", "failing", "running"]


class Service(BaseModel):
    name: str
    owner: str
    status: Status
    build_minutes: float
    coverage: float


class Queue(BaseModel):
    depth: int
    oldest_minutes: int
    by_priority: dict[str, int]


class Release(BaseModel):
    service: str
    version: str
    released_at: datetime


class Radiator(BaseModel):
    generated_at: datetime
    services: list[Service]
    queue: Queue
    releases: list[Release]


def status_for(roll: float) -> Status:
    """Most builds pass; a few run or fail."""
    if roll < 0.1:
        return "failing"
    if roll < 0.25:
        return "running"
    return "passing"


def radiator(now: datetime) -> Radiator:
    minute = now.replace(second=0, microsecond=0)
    rng = random.Random(int(minute.timestamp()))
    services = [
        Service(
            name=name,
            owner=owner,
            status=status_for(rng.random()),
            build_minutes=round(rng.uniform(1, 15), 1),
            coverage=round(rng.uniform(0.6, 0.95), 2),
        )
        for name, owner in SERVICES.items()
    ]
    by_priority = {p: rng.randint(0, 2 if p in ("P0", "P1") else 6) for p in PRIORITIES}
    depth = sum(by_priority.values())
    queue = Queue(depth=depth, oldest_minutes=rng.randint(1, 30) if depth else 0, by_priority=by_priority)
    releases = sorted(
        (
            Release(
                service=name,
                version=f"0.{rng.randint(1, 9)}.{rng.randint(0, 20)}",
                released_at=minute - timedelta(minutes=rng.randint(5, 600)),
            )
            for name in rng.sample(sorted(SERVICES), 5)
        ),
        key=lambda r: r.released_at,
        reverse=True,
    )
    return Radiator(generated_at=now, services=services, queue=queue, releases=releases)
