"""Step 0 — classify the company so later steps know where to look.

Cheap parametric call: sector bucket, a search-friendly sector query, a one-line
overview, and the main competitors. These frame the sector and competitor
retrieval passes. Numbers are NOT asked for here — only the framing.
"""
from . import llm

SYSTEM = """You are a market analyst. Given a company name, classify it. Use only \
what you're confident about; if you don't recognise the company, say so.

Return JSON:
{
  "known": true/false,               // do you actually recognise this company?
  "sector": "short vertical label, e.g. FMCG, Audio Entertainment, Cloud SaaS",
  "sector_query": "2-4 word search phrase for the sector's market, e.g. \
'FMCG India market' or 'audio streaming market'",
  "overview": "one factual sentence on what the company does",
  "competitors": ["3-5 main competitors by name"]
}"""


async def classify(company: str) -> dict:
    data = await llm.chat_json(
        SYSTEM, f"Company: {company}\nClassify it now.", temperature=0.1
    )
    return {
        "known": bool(data.get("known", True)),
        "sector": data.get("sector") or "Unknown",
        "sector_query": data.get("sector_query") or (data.get("sector") or company),
        "overview": data.get("overview") or "",
        "competitors": [c for c in (data.get("competitors") or []) if isinstance(c, str)][:5],
    }
