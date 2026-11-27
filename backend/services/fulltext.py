"""Full text for question answering: fetch → extract → chunk.

arXiv papers are downloaded as PDF from the export.arxiv.org mirror and parsed with
pypdf (pure Python). Everything else — and any PDF that fails — falls back to the
abstract, so every paper contributes at least one passage. The reference list is
cut off: it is noise for retrieval.
"""

from __future__ import annotations

import io
import logging
import re

import httpx

from agents.discovery import normalize_arxiv_id, normalize_doi

logger = logging.getLogger(__name__)

ARXIV_PDF = "https://export.arxiv.org/pdf/{id}"
MAX_PDF_BYTES = 15 * 1024 * 1024
MAX_PAGES = 30
CHUNK_CHARS = 1000
OVERLAP_CHARS = 150
MAX_CHUNKS_PER_PAPER = 40  # ~40k characters: intro, method, results
_REFERENCES = re.compile(r"\n\s*(references|bibliography|literature cited)\s*\n", re.I)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def arxiv_id_of(external_id: str | None) -> str | None:
    if external_id and external_id.startswith("arxiv:"):
        return normalize_arxiv_id(external_id.removeprefix("arxiv:"))
    return None


def clean_text(raw: str) -> str:
    text = raw.replace("\r", "\n")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # re-join words hyphenated at line ends
    match = _REFERENCES.search(text)
    if match and match.start() > len(text) * 0.4:  # only a references heading late in the paper
        text = text[: match.start()]
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    return re.sub(r"(?<!\n)\n(?!\n)", " ", text).strip()


def chunk_text(text: str, size: int = CHUNK_CHARS, overlap: int = OVERLAP_CHARS) -> list[str]:
    """Sentence-aligned chunks of about ``size`` characters with ``overlap`` carried over."""
    sentences = [s.strip() for s in _SENTENCE_END.split(text) if s.strip()]
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        while len(sentence) > size:  # pathological run-on text: hard split
            if current:
                chunks.append(current)
                current = ""
            chunks.append(sentence[:size])
            sentence = sentence[size - overlap :]
        if current and len(current) + 1 + len(sentence) > size:
            chunks.append(current)
            current = current[-overlap:].split(" ", 1)[-1] if overlap else ""
        current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current)
    return [c for c in chunks if len(c) > 40]


def pdf_to_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = []
    for page in reader.pages[:MAX_PAGES]:
        try:
            pages.append(page.extract_text() or "")
        except Exception:  # a broken page should not lose the whole paper
            continue
    return "\n".join(pages)


async def fetch_arxiv_text(client: httpx.AsyncClient, arxiv_id: str) -> str | None:
    try:
        response = await client.get(ARXIV_PDF.format(id=arxiv_id))
        if response.status_code != 200 or len(response.content) > MAX_PDF_BYTES:
            return None
        if not response.content.startswith(b"%PDF"):
            return None
        import asyncio

        text = await asyncio.to_thread(pdf_to_text, response.content)
        cleaned = clean_text(text)
        return cleaned if len(cleaned) > 2000 else None  # scanned/empty PDFs → abstract
    except Exception as exc:
        logger.info("Full text unavailable for arXiv %s: %s", arxiv_id, exc)
        return None


_ARXIV_IN_URL = re.compile(r"arxiv\.org/(?:abs|pdf)/([^?#\s]+?)(?:\.pdf)?(?:[?#]|$)", re.I)


async def resolve_sources(client: httpx.AsyncClient, dois: list[str]) -> dict[str, tuple[str, str]]:
    """``{doi: ("arxiv", id) | ("url", pdf_url)}`` from OpenAlex locations.

    An arXiv copy is preferred (stable host, reliable PDFs); otherwise the best
    open-access PDF link, if any.
    """
    from agents.discovery import fetch_with_retry
    from config import get_settings

    s = get_settings()
    found: dict[str, tuple[str, str]] = {}
    for start in range(0, len(dois), 50):
        chunk = dois[start : start + 50]
        params = {
            "filter": "doi:" + "|".join(chunk),
            "per_page": 50,
            "select": "doi,best_oa_location,locations",
        }
        if s.openalex_mailto:
            params["mailto"] = s.openalex_mailto
        response = await fetch_with_retry(client, s.openalex_url, params)
        for item in (response.json().get("results") if response else None) or []:
            doi = normalize_doi(item.get("doi"))
            urls = [
                u
                for loc in item.get("locations") or []
                for u in (loc.get("landing_page_url"), loc.get("pdf_url"))
                if u
            ]
            arxiv = next((m.group(1) for u in urls if (m := _ARXIV_IN_URL.search(u))), None)
            if arxiv:
                found[doi] = ("arxiv", normalize_arxiv_id(arxiv))
            elif (item.get("best_oa_location") or {}).get("pdf_url"):
                found[doi] = ("url", item["best_oa_location"]["pdf_url"])
    return found


async def fetch_pdf_text(client: httpx.AsyncClient, url: str) -> str | None:
    """Any open-access PDF URL (publisher sites may refuse bots; that is fine)."""
    try:
        response = await client.get(url)
        if response.status_code != 200 or len(response.content) > MAX_PDF_BYTES:
            return None
        if not response.content.startswith(b"%PDF"):
            return None
        import asyncio

        cleaned = clean_text(await asyncio.to_thread(pdf_to_text, response.content))
        return cleaned if len(cleaned) > 2000 else None
    except Exception as exc:
        logger.info("Open-access PDF unavailable (%s): %s", url, exc)
        return None


def passages_for(title: str, abstract: str | None, full_text: str | None) -> tuple[list[str], str]:
    """``(chunks, source)`` where source is "fulltext" or "abstract"."""
    if full_text:
        return chunk_text(full_text)[:MAX_CHUNKS_PER_PAPER], "fulltext"
    text = f"{title}. {abstract or ''}".strip()
    return (chunk_text(text) or [text]), "abstract"
