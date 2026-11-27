"""End-to-end API tests: real FastAPI app, real SQLite, deterministic agents."""

import time

from tests.conftest import USER_A, USER_B


def _new_session(client, query="graph neural networks drug discovery"):
    r = client.post("/sessions", json={"name": "GNN", "query": query})
    assert r.status_code == 201, r.text
    return r.json()["id"]


class TestHealth:
    def test_health_reports_db_and_llm(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["database"] == "ok"
        assert body["llm_enabled"] is False
        assert r.headers["X-Request-ID"]
        assert r.headers["X-Content-Type-Options"] == "nosniff"


class TestAuthRequired:
    def test_endpoints_reject_missing_token(self):
        from fastapi.testclient import TestClient

        from main import app

        with TestClient(app) as c:
            for method, path in [
                ("get", "/sessions"),
                ("post", "/sessions"),
                ("get", "/digests"),
                ("get", "/auth/me"),
                ("post", "/sessions/x/orchestrate"),
            ]:
                r = getattr(c, method)(path)
                assert r.status_code == 401, (method, path, r.text)

    def test_register_rejects_mismatched_passwords(self, client):
        r = client.post(
            "/auth/register",
            json={
                "email": "a@example.com",
                "username": "alice",
                "password": "Secure#Pass1",
                "confirm_password": "Other#Pass1",
            },
        )
        assert r.status_code == 422
        assert "Passwords do not match" in r.text


class TestSessions:
    def test_create_list_get(self, client):
        sid = _new_session(client)
        listed = client.get("/sessions").json()
        assert any(s["id"] == sid and s["paper_count"] == 0 for s in listed)
        full = client.get(f"/sessions/{sid}").json()
        assert full["papers"] == [] and full["user_id"] == USER_A

    def test_rejects_script_injection(self, client):
        r = client.post("/sessions", json={"name": "<script>x", "query": "q"})
        assert r.status_code == 422

    def test_other_users_cannot_see_session(self, client):
        sid = _new_session(client)
        client.current_user["id"] = USER_B
        assert client.get(f"/sessions/{sid}").status_code == 404
        assert client.post(f"/sessions/{sid}/orchestrate").status_code == 404
        assert all(s["id"] != sid for s in client.get("/sessions").json())
        client.current_user["id"] = USER_A

    def test_delete(self, client):
        sid = _new_session(client)
        assert client.delete(f"/sessions/{sid}").status_code == 204
        assert client.get(f"/sessions/{sid}").status_code == 404


class TestOrchestration:
    def test_full_run_persists_everything(self, client, fake_sources):
        sid = _new_session(client)
        r = client.post(f"/sessions/{sid}/orchestrate")
        assert r.status_code == 200, r.text
        body = r.json()

        agents = {t["agent"]: t["status"] for t in body["trace"]}
        assert agents == {
            "Manager": "done",
            "Discovery": "done",
            "Analysis": "done",
            "Citation": "done",
            "Summarizer": "done",
            "Conflict Detection": "done",
            "Roadmap": "done",
        }
        assert len(body["papers"]) == 12
        assert all(p["id"] and p["session_id"] == sid for p in body["papers"])
        assert all(p["citation"]["apa"] for p in body["papers"])
        # Summaries are linked to real paper ids (they were never saved before).
        paper_ids = {p["id"] for p in body["papers"]}
        assert len(body["summaries"]) == 10
        assert {s["paper_id"] for s in body["summaries"]} <= paper_ids
        assert body["roadmap"]["foundational_papers"]
        assert {fp["paper_id"] for fp in body["roadmap"]["foundational_papers"]} <= paper_ids
        assert body["analysis"]["publication_trend"]

        full = client.get(f"/sessions/{sid}").json()
        assert len(full["papers"]) == 12
        assert sum(1 for p in full["papers"] if p["summary"]) == 10
        assert len(full["analyses"]) == 1
        assert client.get(f"/sessions/{sid}/roadmap").status_code == 200

    def test_rerun_is_idempotent(self, client, fake_sources):
        sid = _new_session(client)
        first = client.post(f"/sessions/{sid}/orchestrate").json()
        second = client.post(f"/sessions/{sid}/orchestrate").json()
        assert len(second["papers"]) == len(first["papers"]) == 12
        full = client.get(f"/sessions/{sid}").json()
        assert len(full["analyses"]) == 1
        assert len(full["conflicts"]) == len(first["conflicts"])

    def test_roadmap_query_adds_papers_to_session(self, client, fake_sources, monkeypatch):
        from agents import discovery
        from tests.conftest import make_paper

        sid = _new_session(client)
        client.post(f"/sessions/{sid}/orchestrate")

        async def other(query, page=0, limit=None, since=None, sources=discovery.SOURCES):
            return [make_paper(i) for i in range(50, 55)], {}

        monkeypatch.setattr(discovery, "fetch_all_sources", other)
        r = client.post(f"/sessions/{sid}/roadmap/query", params={"query": "gnn survey"})
        assert r.status_code == 200, r.text
        assert r.json()["triggered_query"] == "gnn survey"
        assert len(client.get(f"/sessions/{sid}").json()["papers"]) == 17

    def test_regenerate_roadmap_uses_stored_data(self, client, fake_sources):
        sid = _new_session(client)
        client.post(f"/sessions/{sid}/orchestrate")
        calls_before = len(fake_sources)
        r = client.post(f"/sessions/{sid}/roadmap")
        assert r.status_code == 200
        assert len(fake_sources) == calls_before  # no new discovery round-trip
        assert r.json()["next_query_suggestions"]

    def test_roadmap_requires_papers(self, client):
        sid = _new_session(client)
        assert client.post(f"/sessions/{sid}/roadmap").status_code == 409


class TestPaperFeatures:
    def _run(self, client):
        sid = _new_session(client)
        papers = client.post(f"/sessions/{sid}/orchestrate").json()["papers"]
        return sid, papers

    def test_note_upsert(self, client, fake_sources):
        _, papers = self._run(client)
        pid = papers[0]["id"]
        assert client.patch(f"/papers/{pid}/note", json={"content": "v1"}).status_code == 200
        r = client.patch(f"/papers/{pid}/note", json={"content": "v2"})
        assert r.json()["content"] == "v2"
        client.current_user["id"] = USER_B
        assert client.patch(f"/papers/{pid}/note", json={"content": "x"}).status_code == 404
        client.current_user["id"] = USER_A

    def test_synthesize(self, client, fake_sources):
        sid, papers = self._run(client)
        ids = [p["id"] for p in papers[:3]]
        r = client.post(f"/sessions/{sid}/synthesize", json={"paper_ids": ids})
        assert r.status_code == 200, r.text
        assert r.json()["content"].startswith("Key claims")
        assert sorted(r.json()["paper_ids"]) == sorted(ids)

    def test_synthesize_rejects_foreign_papers(self, client, fake_sources):
        sid, _ = self._run(client)
        r = client.post(f"/sessions/{sid}/synthesize", json={"paper_ids": ["nope"]})
        assert r.status_code == 404

    def test_exports(self, client, fake_sources):
        sid, _ = self._run(client)
        bib = client.get(f"/sessions/{sid}/export/bib")
        assert bib.status_code == 200
        keys = [
            line.split("{", 1)[1].rstrip(",")
            for line in bib.text.splitlines()
            if line.startswith("@")
        ]
        assert len(keys) == 12 and len(set(keys)) == 12  # unique citation keys
        txt = client.get(f"/sessions/{sid}/export/txt", params={"style": "ieee"})
        assert txt.status_code == 200 and txt.text.count("\n\n") == 11

    def test_conflict_resolution_and_redetection(self, client, fake_sources):
        sid, _ = self._run(client)
        conflicts = client.get(f"/sessions/{sid}/conflicts").json()
        if conflicts:
            cid = conflicts[0]["id"]
            r = client.post(
                f"/sessions/{sid}/conflicts/{cid}/resolve", json={"resolution_notes": "ok"}
            )
            assert r.status_code == 200
        r = client.post(f"/sessions/{sid}/detect-conflicts")
        assert r.status_code == 200
        body = r.json()
        assert "summary" in body
        assert all(c["id"] and c["session_id"] == sid for c in body["conflicts"])
        if conflicts:  # the resolved one survives re-detection
            assert any(c["resolved"] for c in body["conflicts"])


class TestDigests:
    def test_crud_and_manual_run(self, client, monkeypatch):
        from datetime import UTC, datetime

        from agents import discovery
        from tests.conftest import make_paper

        today = datetime.now(UTC).date().isoformat()
        old = make_paper(99, publication_date="2001-01-01", year=2001)

        async def recent(query, page=0, limit=None, since=None, sources=discovery.SOURCES):
            assert since is not None  # digests always ask sources for a date window
            # 1 is already in one of this user's sessions (another test) → not new.
            fresh = [make_paper(i, publication_date=today) for i in (501, 502, 503)]
            return fresh + [make_paper(1, publication_date=today), old], {}

        monkeypatch.setattr(discovery, "fetch_all_sources", recent)
        from database import get_db_context
        from services import persistence

        seen_sid = client.post("/sessions", json={"name": "seen", "query": "x"}).json()["id"]
        with get_db_context() as db:  # paper 1 is already in another of this user's sessions
            persistence.save_papers(db, seen_sid, [make_paper(1)])
        r = client.post("/digests", json={"name": "GNN weekly", "query": "gnn drug"})
        assert r.status_code == 201, r.text
        did = r.json()["id"]
        assert r.json()["next_run_at"]

        run = client.post(f"/digests/{did}/run")
        assert run.status_code == 202
        run_id = run.json()["id"]

        deadline = time.time() + 10
        status = "running"
        while time.time() < deadline and status == "running":
            time.sleep(0.1)
            runs = client.get(f"/digests/{did}").json()["runs"]
            status = next(x["status"] for x in runs if x["id"] == run_id)
        assert status == "completed"
        runs = client.get(f"/digests/{did}").json()["runs"]
        assert len(runs) == 1  # the manual run is not recorded twice
        # 3 new papers: the stale one is dropped, and paper 1 was seen in another session
        assert runs[0]["new_papers_count"] == 3 and runs[0]["session_id"]
        digest_session = client.get(f"/sessions/{runs[0]['session_id']}")
        assert digest_session.status_code == 200  # owned by the digest's user
        assert sum(1 for p in digest_session.json()["papers"] if p["summary"]) > 0

        toggled = client.patch(f"/digests/{did}/toggle").json()
        assert toggled["is_active"] is False
        assert client.get(f"/digests/{did}/preview").status_code == 200
        client.current_user["id"] = USER_B
        assert client.get(f"/digests/{did}").status_code == 404
        client.current_user["id"] = USER_A
        assert client.delete(f"/digests/{did}").status_code == 200
        assert client.get(f"/digests/{did}").status_code == 404

    def test_invalid_frequency(self, client):
        r = client.post("/digests", json={"name": "x", "query": "y", "frequency": "hourly"})
        assert r.status_code == 422
