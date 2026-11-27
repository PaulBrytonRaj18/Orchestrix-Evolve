"""Shared fixtures. Environment is fixed *before* any app module is imported."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_DB_FILE = Path(tempfile.mkdtemp(prefix="orchestrix-tests-")) / "test.db"
os.environ.update(
    {
        "ENV": "test",
        # Point TEST_DATABASE_URL at a scratch Postgres to run the suite there too.
        "DATABASE_URL": os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_DB_FILE}"),
        "SUPABASE_DB_URL": "",
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_SERVICE_KEY": "service-role-key-for-tests",
        "SUPABASE_JWT_SECRET": "unit-test-jwt-secret-with-enough-length-0123456789",
        "GROQ_API_KEY": "",
        "ORCHESTRATOR_PLANNER": "static",
        "ENABLE_SCHEDULER": "true",
        "LOG_LEVEL": "WARNING",
        # No model downloads in tests; tests that need vectors use FakeEmbedder.
        "EMBEDDINGS_ENABLED": "false",
    }
)

import pytest  # noqa: E402

from agents import discovery  # noqa: E402
from auth import get_current_user  # noqa: E402
from database import init_db  # noqa: E402
from rate_limit import limiter  # noqa: E402

init_db()

USER_A = "user-a"
USER_B = "user-b"


def make_paper(i: int, **overrides) -> dict:
    base = {
        "title": f"Graph neural networks for molecular property prediction study {i}",
        "authors": [f"Alice Author{i}", "Bob Builder"],
        "year": 2018 + (i % 7),
        "abstract": (
            f"We propose model {i} using graph neural networks for drug discovery. "
            "Our approach improves molecular property prediction on benchmark datasets. "
            "However, a limitation is the small size of available labelled data."
        ),
        "source_url": f"https://arxiv.org/abs/2401.{1000 + i}",
        "citation_count": 10 * i,
        "source": "arxiv" if i % 2 else "openalex",
        "venue": "NeurIPS" if i % 3 == 0 else "arXiv",
        "doi": f"10.1000/test.{i}" if i % 2 == 0 else None,
        "arxiv_id": f"2401.{1000 + i}" if i % 2 else None,
        "publication_date": f"{2018 + (i % 7)}-06-01",
    }
    base["external_id"] = base["doi"] or f"arxiv:{base['arxiv_id']}"
    base.update(overrides)
    return base


@pytest.fixture(autouse=True)
def _empty_source_cache():
    """Every test starts with a cold source cache (memory and table)."""
    from sqlalchemy import delete

    from agents.discovery import reset_cooldowns
    from database import get_db_context
    from models import SourceCacheEntry
    from services.cache import source_cache

    source_cache.clear_memory()
    reset_cooldowns()
    with get_db_context() as db:
        db.execute(delete(SourceCacheEntry))
    yield


@pytest.fixture
def fake_sources(monkeypatch):
    """Replace network fetching with 12 deterministic papers."""
    calls: list[dict] = []

    async def fake_fetch(query, page=0, limit=None, since=None, sources=discovery.SOURCES):
        calls.append({"query": query, "page": page, "since": since})
        stats = {s: {"status": "ok", "count": 4, "ms": 1} for s in sources}
        return [make_paper(i) for i in range(1, 13)], stats

    monkeypatch.setattr(discovery, "fetch_all_sources", fake_fetch)
    return calls


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from main import app

    current = {"id": USER_A}
    app.dependency_overrides[get_current_user] = lambda: current["id"]
    limiter.reset()
    with TestClient(app, raise_server_exceptions=False) as c:
        c.current_user = current
        yield c
    app.dependency_overrides.clear()


class FakeEmbedder:
    """Deterministic stand-in for the ONNX model: hashed bag-of-words, L2-normalised."""

    model_name = "fake/bow-64"
    dim = 64
    available = True

    def _vec(self, text):
        import hashlib

        import numpy as np

        v = np.zeros(self.dim, dtype=np.float32)
        for word in text.lower().split():
            v[int(hashlib.md5(word.strip(".,:;").encode()).hexdigest(), 16) % self.dim] += 1.0
        n = np.linalg.norm(v)
        return v / n if n else v

    def embed_documents(self, texts):
        import numpy as np

        return np.asarray([self._vec(t) for t in texts], dtype=np.float32).reshape(
            len(texts), self.dim
        )

    def embed_query(self, text):
        return self._vec(text)


@pytest.fixture
def fake_embedder(monkeypatch):
    from services import embeddings, qa, related

    emb = FakeEmbedder()
    for module in (embeddings, related, qa):
        monkeypatch.setattr(module, "get_embedder", lambda: emb)
    return emb
