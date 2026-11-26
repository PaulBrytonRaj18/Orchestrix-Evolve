"""Two-level cache for discovery-source responses.

Level 1 is an in-process LRU (no I/O); level 2 is the ``source_cache`` table, so
every replica and the digest scheduler share results. Only successful fetches are
stored (failures raise before reaching :meth:`SourceCache.set`). Cache problems are
logged and treated as misses — they never fail a search.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import logging
import random
import time
from collections import OrderedDict
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select

from config import get_settings

logger = logging.getLogger(__name__)


def _normalise_query(query: str) -> str:
    return " ".join(query.lower().split())


class SourceCache:
    def __init__(self) -> None:
        self._mem: OrderedDict[str, tuple[float, list[dict[str, Any]]]] = OrderedDict()
        self.hits = 0
        self.misses = 0

    @staticmethod
    def make_key(source: str, query: str, page: int, limit: int, since: date | None) -> str:
        raw = json.dumps(
            [source, _normalise_query(query), page, limit, since.isoformat() if since else None]
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    @property
    def enabled(self) -> bool:
        return get_settings().source_cache_enabled

    def clear_memory(self) -> None:
        self._mem.clear()
        self.hits = self.misses = 0

    # ── memory level ───────────────────────────────────────────────────────
    def _mem_get(self, key: str) -> list[dict[str, Any]] | None:
        item = self._mem.get(key)
        if item is None:
            return None
        expires, papers = item
        if expires < time.time():
            self._mem.pop(key, None)
            return None
        self._mem.move_to_end(key)
        return papers

    def _mem_set(self, key: str, papers: list[dict[str, Any]], ttl: int) -> None:
        cap = get_settings().source_cache_memory_items
        if cap <= 0:
            return
        self._mem[key] = (time.time() + ttl, papers)
        self._mem.move_to_end(key)
        while len(self._mem) > cap:
            self._mem.popitem(last=False)

    # ── database level ─────────────────────────────────────────────────────
    @staticmethod
    def _db_get(key: str) -> tuple[list[dict[str, Any]], float] | None:
        from database import get_db_context
        from models import SourceCacheEntry

        with get_db_context() as db:
            row = db.scalar(select(SourceCacheEntry).where(SourceCacheEntry.key == key))
            if row is None:
                return None
            expires = row.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=UTC)
            if expires <= datetime.now(UTC):
                return None
            return row.payload, expires.timestamp()

    @staticmethod
    def _db_set(key: str, source: str, papers: list[dict[str, Any]], ttl: int) -> None:
        from database import get_db_context
        from models import SourceCacheEntry

        now = datetime.now(UTC)
        with get_db_context() as db:
            row = db.get(SourceCacheEntry, key)
            if row is None:
                row = SourceCacheEntry(key=key, source=source)
                db.add(row)
            row.payload = papers
            row.expires_at = now + timedelta(seconds=ttl)
            if random.random() < 0.02:  # opportunistic purge of expired rows
                db.execute(delete(SourceCacheEntry).where(SourceCacheEntry.expires_at < now))

    # ── public API ─────────────────────────────────────────────────────────
    async def get(self, key: str) -> list[dict[str, Any]] | None:
        if not self.enabled:
            return None
        papers = self._mem_get(key)
        if papers is None:
            try:
                found = await asyncio.to_thread(self._db_get, key)
            except Exception as exc:
                logger.warning("Source cache read failed: %s", exc)
                found = None
            if found is not None:
                papers, expires = found
                self._mem_set(key, papers, max(int(expires - time.time()), 1))
        if papers is None:
            self.misses += 1
            return None
        self.hits += 1
        return copy.deepcopy(papers)  # callers mutate papers (ids, scores)

    async def set(
        self, key: str, source: str, papers: list[dict[str, Any]], is_since_query: bool
    ) -> None:
        if not self.enabled:
            return
        s = get_settings()
        ttl = s.source_cache_since_ttl_seconds if is_since_query else s.source_cache_ttl_seconds
        if ttl <= 0:
            return
        stored = copy.deepcopy(papers)
        self._mem_set(key, stored, ttl)
        try:
            await asyncio.to_thread(self._db_set, key, source, stored, ttl)
        except Exception as exc:
            logger.warning("Source cache write failed: %s", exc)


source_cache = SourceCache()
