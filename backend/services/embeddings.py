"""Local, free text embeddings (fastembed / ONNX Runtime — no PyTorch, no API key).

The model is downloaded once from Hugging Face on first use (into
``EMBEDDING_CACHE_DIR``) and then runs on CPU. If it cannot be loaded (offline,
disabled, low memory) every caller falls back to TF-IDF, so search keeps working.

Each supported model is used with the query/document prefixes it was trained with;
using the wrong ones measurably hurts retrieval quality.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

import numpy as np

from config import get_settings

logger = logging.getLogger(__name__)

_BGE_QUERY = "Represent this sentence for searching relevant passages: "


@dataclass(frozen=True)
class ModelSpec:
    dim: int
    query_prefix: str = ""
    doc_prefix: str = ""


MODELS: dict[str, ModelSpec] = {
    "BAAI/bge-small-en-v1.5": ModelSpec(384, _BGE_QUERY),
    "BAAI/bge-base-en-v1.5": ModelSpec(768, _BGE_QUERY),
    "snowflake/snowflake-arctic-embed-s": ModelSpec(384, _BGE_QUERY),
    "nomic-ai/nomic-embed-text-v1.5-Q": ModelSpec(768, "search_query: ", "search_document: "),
}


def document_text(paper: dict, max_chars: int | None = None) -> str:
    """What gets embedded for a paper: its title and the start of its abstract.

    Cost grows with length, so text is cut at ``EMBEDDING_MAX_CHARS`` (chosen with the
    evaluation set as the best quality/latency trade-off).
    """
    max_chars = max_chars or get_settings().embedding_max_chars
    title = (paper.get("title") or "").strip()
    abstract = (paper.get("abstract") or "").strip()
    text = f"{title}. {abstract}" if abstract else title
    return text[:max_chars]


class Embedder:
    def __init__(self, model_name: str) -> None:
        if model_name not in MODELS:
            raise ValueError(
                f"Unsupported embedding model {model_name!r}; choose from {list(MODELS)}"
            )
        self.model_name = model_name
        self.spec = MODELS[model_name]
        self._model = None
        self._lock = threading.Lock()
        self._failed = False

    @property
    def dim(self) -> int:
        return self.spec.dim

    def _load(self):
        if self._model is not None or self._failed:
            return self._model
        with self._lock:
            if self._model is None and not self._failed:
                s = get_settings()
                try:
                    from fastembed import TextEmbedding

                    self._model = TextEmbedding(
                        self.model_name,
                        cache_dir=s.embedding_cache_dir or None,
                        threads=s.embedding_threads or None,
                    )
                    logger.info("Loaded embedding model %s", self.model_name)
                except Exception as exc:  # offline, missing files, out of memory…
                    self._failed = True
                    logger.warning("Embedding model unavailable (%s); using TF-IDF", exc)
        return self._model

    @property
    def available(self) -> bool:
        return self._load() is not None

    def _embed(self, texts: list[str]) -> np.ndarray:
        model = self._load()
        if model is None:
            raise RuntimeError("embedding model unavailable")
        vectors = np.asarray(list(model.embed(texts, batch_size=16)), dtype=np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors / np.where(norms == 0, 1.0, norms)

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        """L2-normalised document vectors, shape (n, dim). Blocking: run in a thread."""
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return self._embed([self.spec.doc_prefix + t for t in texts])

    def embed_query(self, text: str) -> np.ndarray:
        return self._embed([self.spec.query_prefix + text])[0]


_embedder: Embedder | None = None
_embedder_lock = threading.Lock()


def get_embedder() -> Embedder | None:
    """The configured embedder, or ``None`` when embeddings are disabled."""
    global _embedder
    s = get_settings()
    if not s.embeddings_enabled:
        return None
    with _embedder_lock:
        if _embedder is None or _embedder.model_name != s.embedding_model:
            _embedder = Embedder(s.embedding_model)
    return _embedder


def reset_embedder() -> None:
    global _embedder
    _embedder = None
