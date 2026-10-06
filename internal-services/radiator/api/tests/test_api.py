from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from radiator_api import app
from radiator_api.data import SERVICES, radiator, status_for
from radiator_api.openapi import schema

client = TestClient(app)
NOON = datetime(2026, 10, 6, 12, 0, 30, tzinfo=UTC)


def test_healthz():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_radiator_lists_every_service():
    body = client.get("/api/radiator").json()
    assert [s["name"] for s in body["services"]] == list(SERVICES)
    assert {s["status"] for s in body["services"]} <= {"passing", "failing", "running"}


def test_queue_depth_is_the_sum_of_its_priorities():
    queue = radiator(NOON).queue
    assert list(queue.by_priority) == ["P0", "P1", "P2", "P3", "P4"]
    assert queue.depth == sum(queue.by_priority.values())


def test_releases_are_newest_first():
    releases = radiator(NOON).releases
    assert len(releases) == 5
    assert [r.released_at for r in releases] == sorted((r.released_at for r in releases), reverse=True)


def test_data_is_stable_within_a_minute_and_changes_after_it():
    same = radiator(NOON.replace(second=59))
    later = radiator(NOON.replace(minute=1))
    assert radiator(NOON).services == same.services
    assert radiator(NOON).services != later.services


def test_status_thresholds():
    assert status_for(0.05) == "failing"
    assert status_for(0.1) == "running"
    assert status_for(0.24) == "running"
    assert status_for(0.25) == "passing"


def test_published_contract_matches_the_code():
    published = (Path(__file__).parent.parent / "openapi.json").read_text()
    assert published == schema(), "openapi.json is stale: run python -m radiator_api.openapi > openapi.json"
