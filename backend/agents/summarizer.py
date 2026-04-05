import httpx
import json
import os
from dotenv import load_dotenv
from typing import List, Dict

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


async def summarize_paper(paper: Dict) -> Dict:
    """
    Generates a structured summary for a single paper using Gemini.
    Returns: abstract_compression, key_contributions, methodology, limitations
    """
    abstract = paper.get("abstract", "")
    title = paper.get("title", "Unknown Title")

    prompt = f"""You are an academic paper summarizer. Given the abstract below, provide a structured summary with exactly four fields.

Paper Title: {title}
Abstract: {abstract}

Return ONLY a valid JSON object with exactly these four keys:
- "abstract_compression": A 2-3 sentence plain-language summary of what the paper is about
- "key_contributions": A bullet list of the main novel contributions (use newlines between items)
- "methodology": A brief description of the methods or approach used (1-2 sentences)
- "limitations": Known or inferred limitations of the work (1-2 sentences)

Do not include any other text, explanation, or markdown formatting.

Example format:
{{"abstract_compression": "This paper presents...", "key_contributions": "• Introduced a novel approach...\\n• Demonstrated improved...\\n• Extended previous work...", "methodology": "The authors employed...", "limitations": "The study is limited by..."}}"""

    if not abstract:
        return {
            "abstract_compression": "No abstract available.",
            "key_contributions": "Information not available.",
            "methodology": "Information not available.",
            "limitations": "Information not available.",
        }

    if not GEMINI_API_KEY:
        return {
            "abstract_compression": f"Summary of: {title}. {abstract[:200]}...",
            "key_contributions": "Gemini API key not configured.",
            "methodology": "Gemini API key not configured.",
            "limitations": "Gemini API key not configured.",
        }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048},
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

            summary = json.loads(text)
            return {
                "abstract_compression": summary.get("abstract_compression", ""),
                "key_contributions": summary.get("key_contributions", ""),
                "methodology": summary.get("methodology", ""),
                "limitations": summary.get("limitations", ""),
            }
    except json.JSONDecodeError as e:
        print(f"JSON parsing error for paper summary {title}: {e}")
        return {
            "abstract_compression": f"Summary of: {title}",
            "key_contributions": "Error generating summary.",
            "methodology": "Error generating summary.",
            "limitations": "Error generating summary.",
        }
    except Exception as e:
        print(f"Summary generation error for paper {title}: {e}")
        return {
            "abstract_compression": f"Summary of: {title}",
            "key_contributions": "Error generating summary.",
            "methodology": "Error generating summary.",
            "limitations": "Error generating summary.",
        }


async def synthesize_papers(papers: List[Dict]) -> str:
    """
    Synthesizes multiple papers into a cohesive paragraph identifying:
    - Common themes across papers
    - Contradictions or disagreements
    - Research gaps or open questions
    """
    if not papers:
        return "No papers selected for synthesis."

    papers_info = []
    for i, paper in enumerate(papers, 1):
        title = paper.get("title", "Unknown Title")
        abstract = paper.get("abstract", "No abstract available.")
        year = paper.get("year", "Unknown")
        authors = paper.get("authors", ["Unknown"])
        authors_str = ", ".join(authors[:3])
        if len(authors) > 3:
            authors_str += " et al."
        papers_info.append(
            f'Paper {i}: "{title}" by {authors_str} ({year}). Abstract: {abstract[:500]}...'
        )

    papers_text = "\n\n".join(papers_info)

    prompt = f"""You are an academic research synthesizer. Given the following papers, write a single cohesive paragraph that:
1. Identifies common themes across the papers
2. Notes any contradictions or disagreements between them
3. Highlights notable research gaps or open questions that none of the papers address

Papers:
{papers_text}

Return ONLY the synthesis paragraph. Do not include any headers, bullet points, or additional text. The paragraph should be 3-5 sentences long and written in academic style."""

    if not GEMINI_API_KEY:
        common_themes = []
        for paper in papers:
            if paper.get("abstract"):
                common_themes.append(paper.get("title", "Unknown"))
        return f"This synthesis covers {len(papers)} papers. Common themes include: {', '.join(common_themes[:3])}. Further analysis requires Gemini API key configuration."

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.5, "maxOutputTokens": 1024},
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
            return text.strip()
    except Exception as e:
        print(f"Synthesis error: {e}")
        return "Error generating synthesis. Please try again."
