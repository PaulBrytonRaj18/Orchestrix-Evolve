"""Citation Generator Agent — APA 7, MLA 9, IEEE and Chicago (author-date)."""

from __future__ import annotations

from typing import Any

UNKNOWN_AUTHOR = "Unknown Author"


def _split_name(name: str) -> tuple[str, list[str]]:
    """Return ``(family, given_names)`` for "Given Family" or "Family, Given"."""
    name = " ".join(name.split())
    if "," in name:
        family, given = (part.strip() for part in name.split(",", 1))
        return family, given.split()
    parts = name.split()
    if len(parts) == 1:
        return parts[0], []
    return parts[-1], parts[:-1]


def _initials(given: list[str]) -> str:
    out = []
    for g in given:
        pieces = [p for p in g.replace(".", " ").split("-") if p.strip()]
        out.append("-".join(f"{p.strip()[0].upper()}." for p in pieces))
    return " ".join(out)


def _clean(authors: list[str] | None) -> list[str]:
    return [a for a in (authors or []) if a and a.strip() and a != "Unknown"]


def _join(items: list[str], conj: str, serial_comma: bool = True) -> str:
    if len(items) <= 1:
        return "".join(items)
    if len(items) == 2:
        return f"{items[0]} {conj} {items[1]}"
    sep = ", " if serial_comma else " "
    return ", ".join(items[:-1]) + f"{sep}{conj} {items[-1]}"


def format_authors_apa(authors: list[str] | None) -> str:
    """APA 7: ``Smith, J., Doe, J. A., & Lee, K.``; 21+ authors → first 19 … last."""
    authors = _clean(authors)
    if not authors:
        return UNKNOWN_AUTHOR
    formatted = []
    for a in authors:
        family, given = _split_name(a)
        ini = _initials(given)
        formatted.append(f"{family}, {ini}" if ini else family)
    if len(formatted) == 1:
        return formatted[0]
    if len(formatted) > 20:
        return ", ".join(formatted[:19]) + ", . . . " + formatted[-1]
    return ", ".join(formatted[:-1]) + ", & " + formatted[-1]


def format_authors_mla(authors: list[str] | None) -> str:
    """MLA 9: ``Smith, John`` / ``Smith, John, and Jane Doe`` / ``Smith, John, et al.``"""
    authors = _clean(authors)
    if not authors:
        return UNKNOWN_AUTHOR
    family, given = _split_name(authors[0])
    first = f"{family}, {' '.join(given)}" if given else family
    if len(authors) == 1:
        return first
    if len(authors) == 2:
        return f"{first}, and {authors[1]}"
    return f"{first}, et al."


def format_authors_ieee(authors: list[str] | None) -> str:
    """IEEE: ``J. Smith, J. Doe, and B. Wilson``; 7+ authors → ``J. Smith et al.``"""
    authors = _clean(authors)
    if not authors:
        return UNKNOWN_AUTHOR
    formatted = []
    for a in authors:
        family, given = _split_name(a)
        ini = _initials(given)
        formatted.append(f"{ini} {family}" if ini else family)
    if len(formatted) > 6:
        return f"{formatted[0]} et al."
    return _join(formatted, "and")


def format_authors_chicago(authors: list[str] | None) -> str:
    """Chicago author-date: ``Smith, John, Jane Doe, and Bob Wilson``; 11+ → first 7 et al."""
    authors = _clean(authors)
    if not authors:
        return UNKNOWN_AUTHOR
    family, given = _split_name(authors[0])
    first = f"{family}, {' '.join(given)}" if given else family
    rest = authors[1:]
    if len(authors) > 10:
        return ", ".join([first, *authors[1:7]]) + ", et al."
    return _join([first, *rest], "and")


def _terminate(text: str) -> str:
    text = text.strip()
    return text if text.endswith((".", "?", "!")) else f"{text}."


def generate_citation(paper: dict[str, Any]) -> dict[str, str]:
    title = " ".join((paper.get("title") or "Untitled").split())
    authors = paper.get("authors") or []
    year = paper.get("year") or "n.d."
    venue = (paper.get("venue") or "").strip()
    doi = paper.get("doi")
    url = f"https://doi.org/{doi}" if doi else (paper.get("source_url") or "")
    tail = f" {url}" if url else ""
    venue_apa = f" *{venue}*." if venue else ""
    venue_q = f" {venue}," if venue else ""

    return {
        "apa": f"{_terminate(format_authors_apa(authors))} ({year}). {_terminate(title)}{venue_apa}{tail}".strip(),
        "mla": f'{_terminate(format_authors_mla(authors))} "{_terminate(title)}"{venue_q} {_terminate(str(year))}{tail}'.strip(),
        "ieee": f'{format_authors_ieee(authors)}, "{title},"{venue_q} {_terminate(str(year))}{tail}'.strip(),
        "chicago": f'{_terminate(format_authors_chicago(authors))} {_terminate(str(year))} "{_terminate(title)}"{venue_q.rstrip(",")}{"." if venue else ""}{tail}'.strip(),
    }


def run(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return copies of ``papers`` with a ``citation`` dict attached."""
    return [{**paper, "citation": generate_citation(paper)} for paper in papers]
