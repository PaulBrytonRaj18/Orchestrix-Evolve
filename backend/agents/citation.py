import httpx
import json
import os
from dotenv import load_dotenv
from typing import List, Dict

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


async def generate_citation(paper: Dict) -> Dict:
    """
    Generates citation strings in APA, MLA, IEEE, and Chicago formats using Gemini.
    """
    title = paper.get("title", "Unknown Title")
    authors = paper.get("authors", [])
    year = paper.get("year", "n.d.")
    source_url = paper.get("source_url", "")

    authors_str = ", ".join(authors) if authors else "Unknown Author"
    if not authors_str:
        authors_str = "Unknown Author"

    prompt = f"""You are an academic citation formatter. Given the following paper information, generate a properly formatted citation in each of the four major citation styles.

Paper Title: {title}
Authors: {authors_str}
Year: {year}
URL: {source_url}

Return ONLY a valid JSON object with exactly these four keys: "apa", "mla", "ieee", and "chicago". Each value should be the citation string in that style. Do not include any other text, explanation, or markdown formatting.

Example format:
{{"apa": "Smith, J. (2020). Title of the paper. Journal Name, 10(2), 1-15.", "mla": "Smith, John. \"Title of the Paper.\" Journal Name, vol. 10, no. 2, 2020, pp. 1-15.", "ieee": "J. Smith, \"Title of the paper,\" Journal Name, vol. 10, no. 2, pp. 1-15, 2020.", "chicago": "Smith, John. \"Title of the Paper.\" Journal Name 10, no. 2 (2020): 1-15."}}"""

    if not GEMINI_API_KEY:
        return {
            "apa": f"{authors_str} ({year}). {title}.",
            "mla": f'{authors_str}. "{title}."',
            "ieee": f'{authors_str}, "{title}," {year}.',
            "chicago": f'{authors_str}. "{title}." {year}.',
        }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048},
                },
            )
            response.raise_for_status()
            data = response.json()

            text = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )

            text = text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            citations = json.loads(text)
            return {
                "apa": citations.get("apa", ""),
                "mla": citations.get("mla", ""),
                "ieee": citations.get("ieee", ""),
                "chicago": citations.get("chicago", ""),
            }
    except json.JSONDecodeError as e:
        print(f"JSON parsing error for paper {title}: {e}")
        return {"apa": "", "mla": "", "ieee": "", "chicago": ""}
    except Exception as e:
        print(f"Citation generation error for paper {title}: {e}")
        return {"apa": "", "mla": "", "ieee": "", "chicago": ""}


async def run(papers: List[Dict]) -> List[Dict]:
    """
    Citation Agent: Generates citations for all papers using Gemini API.
    Returns papers augmented with citation objects.
    """
    if not papers:
        return []

    citation_tasks = [generate_citation(paper) for paper in papers]
    citations_list = await asyncio.gather(*citation_tasks)

    result = []
    for paper, citations in zip(papers, citations_list):
        paper_copy = paper.copy()
        paper_copy["citation"] = citations
        result.append(paper_copy)

    return result


import asyncio
