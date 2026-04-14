from typing import List, Dict

def format_authors_apa(authors):
    if not authors:
        return "Unknown Author"
    return ", ".join(authors)

def format_authors_mla(authors):
    if not authors:
        return "Unknown Author"
    return authors[0] + (" et al." if len(authors) > 1 else "")

def format_authors_ieee(authors):
    if not authors:
        return "Unknown Author"
    return ", ".join(authors)

def format_authors_chicago(authors):
    if not authors:
        return "Unknown Author"
    return ", ".join(authors)


def generate_citation(paper: Dict) -> Dict:
    title = paper.get("title", "Unknown Title")
    authors = paper.get("authors", [])
    year = paper.get("year", "n.d.")
    url = paper.get("source_url", "")

    apa = f"{format_authors_apa(authors)} ({year}). {title}. {url}"
    mla = f'{format_authors_mla(authors)}. "{title}." {year}. {url}'
    ieee = f'{format_authors_ieee(authors)}, "{title}," {year}. {url}'
    chicago = f'{format_authors_chicago(authors)}. "{title}." ({year}). {url}'

    return {
        "apa": apa,
        "mla": mla,
        "ieee": ieee,
        "chicago": chicago
    }


def run(papers: List[Dict]) -> List[Dict]:
    result = []

    for paper in papers:
        paper_copy = paper.copy()
        paper_copy["citation"] = generate_citation(paper)
        result.append(paper_copy)

    return result


# ✅ TEST
if __name__ == "__main__":
    papers = [
        {
            "title": "Deep Learning for AI",
            "authors": ["John Smith", "Jane Doe"],
            "year": "2023",
            "source_url": "https://example.com"
        }
    ]

    output = run(papers)

    import json
    print(json.dumps(output, indent=2))