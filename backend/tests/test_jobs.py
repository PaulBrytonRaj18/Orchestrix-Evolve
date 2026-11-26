"""Background jobs + Server-Sent Events."""

import asyncio
import json
import threading
import time
from datetime import UTC, datetime, timedelta

import pytest

from tests.conftest import USER_B, make_paper


def _new_session(client, query="graph neural networks drug discovery"):
    r = client.post("/sessions", json={"name": "GNN", "query": query})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def read_events(client, job_id, timeout=15):
    """Consume an SSE stream until done/error; return [(event, data), ...]."""
    events, event = [], None
    deadline = time.time() + timeout
    with client.stream("GET", f"/jobs/{job_id}/events") as r:
        assert r.status_code == 200, r.read()
        assert r.headers["content-type"].startswith("text/event-stream")
        for line in r.iter_lines():
            if time.time() > deadline:
                pytest.fail("stream did not finish in time")
            if line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: "):
                events.append((event, json.loads(line[6:])))
                if event in ("done", "error"):
                    break
    return events


@pytest.fixture
def slow_sources(monkeypatch):
    """Discovery that takes ~0.6 s, so jobs stay active long enough to observe."""
    from agents import discovery

    gate = {"delay": 0.6}

    async def slow(query, page=0, limit=None, since=None, sources=discovery.SOURCES):
        await asyncio.sleep(gate["delay"])
        return [make_paper(i) for i in range(1, 13)], {}

    monkeypatch.setattr(discovery, "fetch_all_sources", slow)
    return gate


def test_job_streams_progress_and_persists(client, fake_sources):
    sid = _new_session(client)
    r = client.post(f"/sessions/{sid}/jobs")
    assert r.status_code == 202, r.text
    job = r.json()
    assert r.headers["Location"] == f"/jobs/{job['id']}"
    assert job["status"] in ("queued", "running") and job["query"].startswith("graph")

    events = read_events(client, job["id"])
    kinds = [e for e, _ in events]
    assert kinds[-1] == "done"
    assert "trace" in kinds and "papers" in kinds
    assert kinds.index("papers") < kinds.index("done")  # papers arrive before the end
    papers_preview = next(d for e, d in events if e == "papers")
    assert len(papers_preview) == 12 and all(p["id"] for p in papers_preview)

    done = events[-1][1]
    assert len(done["papers"]) == 12 and done["roadmap"] and len(done["summaries"]) == 10
    # Provisional ids become the stored ids for new papers, so the preview stays valid.
    assert {p["id"] for p in papers_preview} == {p["id"] for p in done["papers"]}
    agents = {t["agent"] for t in done["trace"]}
    assert {"Discovery", "Summarizer", "Roadmap"} <= agents

    polled = client.get(f"/jobs/{job['id']}").json()
    assert polled["status"] == "completed" and polled["finished_at"]
    assert polled["trace"] and all(t["status"] != "running" for t in polled["trace"])
    assert len(client.get(f"/sessions/{sid}").json()["papers"]) == 12


def test_reconnect_after_completion_replays_from_db(client, fake_sources):
    from services.jobs import job_manager

    sid = _new_session(client)
    job_id = client.post(f"/sessions/{sid}/jobs").json()["id"]
    read_events(client, job_id)
    job_manager._live.pop(job_id, None)  # as if a different process served the reconnect
    events = read_events(client, job_id)
    assert [e for e, _ in events] == ["status", "trace", "done"]
    assert events[0][1] == {"status": "completed"}
    assert len(events[-1][1]["papers"]) == 12


def test_duplicate_submissions_reuse_the_active_job(client, slow_sources):
    sid = _new_session(client)
    first = client.post(f"/sessions/{sid}/jobs").json()
    second = client.post(f"/sessions/{sid}/jobs").json()
    assert first["id"] == second["id"]
    read_events(client, first["id"])
    third = client.post(f"/sessions/{sid}/jobs").json()  # finished → a new run
    assert third["id"] != first["id"]
    read_events(client, third["id"])


def test_active_job_limit_per_user(client, slow_sources, monkeypatch):
    from config import get_settings

    monkeypatch.setattr(get_settings(), "job_max_active_per_user", 1)
    a, b = _new_session(client), _new_session(client)
    job = client.post(f"/sessions/{a}/jobs").json()
    r = client.post(f"/sessions/{b}/jobs")
    assert r.status_code == 429
    read_events(client, job["id"])
    assert client.post(f"/sessions/{b}/jobs").status_code == 202


def test_followup_job_adds_papers_and_keeps_roadmap(client, fake_sources, monkeypatch):
    from agents import discovery

    sid = _new_session(client)
    read_events(client, client.post(f"/sessions/{sid}/jobs").json()["id"])
    roadmap_before = client.get(f"/sessions/{sid}/roadmap").json()

    async def other(query, page=0, limit=None, since=None, sources=discovery.SOURCES):
        return [make_paper(i) for i in range(40, 44)], {}

    monkeypatch.setattr(discovery, "fetch_all_sources", other)
    r = client.post(f"/sessions/{sid}/jobs", json={"kind": "followup", "query": "gnn survey"})
    assert r.status_code == 202 and r.json()["query"] == "gnn survey"
    done = read_events(client, r.json()["id"])[-1][1]
    assert len(done["papers"]) == 16
    assert client.get(f"/sessions/{sid}/roadmap").json() == roadmap_before


def test_followup_requires_query(client):
    sid = _new_session(client)
    assert client.post(f"/sessions/{sid}/jobs", json={"kind": "followup"}).status_code == 422


def test_failed_job_reports_error(client, fake_sources, monkeypatch):
    from services import persistence

    def broken(*_a, **_k):
        raise RuntimeError("disk full")

    monkeypatch.setattr(persistence, "persist_and_view", broken)
    sid = _new_session(client)
    job_id = client.post(f"/sessions/{sid}/jobs").json()["id"]
    events = read_events(client, job_id)
    assert events[-1] == ("error", {"message": "RuntimeError: disk full"})
    job = client.get(f"/jobs/{job_id}").json()
    assert job["status"] == "failed" and "disk full" in job["error"]


def test_jobs_are_private(client, fake_sources):
    sid = _new_session(client)
    job_id = client.post(f"/sessions/{sid}/jobs").json()["id"]
    read_events(client, job_id)
    client.current_user["id"] = USER_B
    try:
        assert client.get(f"/jobs/{job_id}").status_code == 404
        assert client.get(f"/jobs/{job_id}/events").status_code == 404
        assert client.post(f"/sessions/{sid}/jobs").status_code == 404
    finally:
        client.current_user["id"] = "user-a"


def test_session_job_listing(client, fake_sources):
    sid = _new_session(client)
    job_id = client.post(f"/sessions/{sid}/jobs").json()["id"]
    read_events(client, job_id)
    listed = client.get(f"/sessions/{sid}/jobs").json()
    assert listed[0]["id"] == job_id and listed[0]["status"] == "completed"


def _insert_job(session_id, **values):
    from database import get_db_context
    from models import OrchestrationJob

    with get_db_context() as db:
        job = OrchestrationJob(
            session_id=session_id,
            user_id="user-a",
            query="q",
            kind="search",
            page=0,
            trace=[],
            **values,
        )
        db.add(job)
        db.flush()
        return job.id


def test_orphaned_jobs_are_failed_on_startup(client):
    from services.jobs import fail_stale_jobs

    sid = _new_session(client)
    old = datetime.now(UTC) - timedelta(minutes=10)
    stale = _insert_job(sid, status="running", heartbeat_at=old)
    fresh = _insert_job(sid, status="running", heartbeat_at=datetime.now(UTC))
    assert fail_stale_jobs() == 1
    assert client.get(f"/jobs/{stale}").json()["status"] == "failed"
    assert client.get(f"/jobs/{fresh}").json()["status"] == "running"
    # A stream on a running job whose process died ends with an error instead of hanging.
    from database import get_db_context
    from models import OrchestrationJob

    with get_db_context() as db:
        db.get(OrchestrationJob, fresh).heartbeat_at = old
    events = read_events(client, fresh)
    assert events[-1][0] == "error"


def test_stream_follows_a_job_running_elsewhere(client):
    """A job owned by another process: the stream follows its DB row to completion."""
    from database import get_db_context
    from models import OrchestrationJob

    sid = _new_session(client)
    job_id = _insert_job(sid, status="running", heartbeat_at=datetime.now(UTC))

    def other_process():
        time.sleep(1.2)
        with get_db_context() as db:
            job = db.get(OrchestrationJob, job_id)
            job.trace = [{"agent": "Discovery", "status": "done", "timestamp": "t"}]
        time.sleep(1.2)
        with get_db_context() as db:
            db.get(OrchestrationJob, job_id).status = "completed"

    worker = threading.Thread(target=other_process)
    worker.start()
    events = read_events(client, job_id)
    worker.join()
    kinds = [e for e, _ in events]
    assert kinds[0] == "status" and "trace" in kinds and kinds[-1] == "done"
    assert any(e == "trace" and d and d[0]["agent"] == "Discovery" for e, d in events)
