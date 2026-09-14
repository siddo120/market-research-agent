"""Live web retrieval via Tavily, hard-filtered to the credibility whitelist.

Three corpora feed the 6-step brief:
- company     -> financials, moves, risks (Steps 2-4)
- sector      -> TAM / macro growth (Step 1)
- competitor  -> rival moves for whitespace analysis (Step 5)

Every hit must be on the whitelist AND mention a relevant term, or it's dropped.
"""
import asyncio
import re

import httpx

from . import config

TAVILY_URL = "https://api.tavily.com/search"

COMPANY_QUERIES = [
    "{q} revenue ARR profit results earnings",
    "{q} funding round valuation raise",
    "{q} acquisition merger partnership deal",
    "{q} new product launch OR relaunch",
    "{q} shuts down OR discontinues OR exits OR pivot",
    "{q} strategy expansion market share",
    "{q} layoffs OR lawsuit OR CEO OR controversy",
]
SECTOR_QUERIES = [
    "{q} market size revenue",
    "{q} CAGR growth forecast outlook",
    "{q} industry trends {year}",
    "{q} market share leaders competition",
]
COMPETITOR_QUERY = "{q} funding launch acquisition strategy growth"


def _relevant(terms: list[str], hit: dict) -> bool:
    """Keep a hit only if it mentions a distinctive token from any term."""
    text = (hit.get("title", "") + " " + hit.get("content", "")).lower()
    tokens: list[str] = []
    for term in terms:
        toks = re.findall(r"[a-z0-9]+", term.lower())
        long = [t for t in toks if len(t) >= 4]
        tokens.extend(long or toks)
    return any(t in text for t in tokens)


async def _one_search(client: httpx.AsyncClient, query: str, topic: str, days: int) -> list[dict]:
    payload = {
        "api_key": config.TAVILY_API_KEY,
        "query": query,
        "search_depth": "advanced",
        "max_results": config.MAX_RESULTS_PER_QUERY,
        "include_domains": config.WHITELIST_DOMAINS,
        "include_raw_content": False,
    }
    if topic == "news":
        payload["topic"] = "news"
        payload["days"] = days
    try:
        resp = await client.post(TAVILY_URL, json=payload, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        return [{"_error": f"{query}: {exc}"}]

    hits = []
    for r in data.get("results", []):
        url = r.get("url", "")
        label = config.source_label(url)
        if not label:
            continue
        hits.append({
            "query": query, "title": r.get("title", ""), "url": url,
            "source": label, "content": r.get("content", ""),
            "published_date": r.get("published_date", ""),
        })
    return hits


async def _gather(queries: list[str], terms: list[str], topic: str, days: int) -> dict:
    """Run queries concurrently; return deduped, whitelisted, relevant hits."""
    async with httpx.AsyncClient() as client:
        batches = await asyncio.gather(
            *[_one_search(client, q, topic, days) for q in queries]
        )
    seen: set[str] = set()
    results, errors = [], []
    for batch in batches:
        for hit in batch:
            if hit.get("_error"):
                errors.append(hit["_error"])
                continue
            if hit["url"] in seen or not _relevant(terms, hit):
                continue
            seen.add(hit["url"])
            results.append(hit)
    return {"results": results, "errors": errors, "count": len(results)}


async def gather_company(company: str) -> dict:
    queries = [t.format(q=company) for t in COMPANY_QUERIES]
    return await _gather(queries, [company], "news", config.RETRIEVAL_DAYS)


async def gather_sector(sector_query: str, year: int = 2026) -> dict:
    queries = [t.format(q=sector_query, year=year) for t in SECTOR_QUERIES]
    # General topic (not news) so market-size/report pages are eligible.
    return await _gather(queries, [sector_query], "general", config.RETRIEVAL_DAYS)


async def gather_competitors(competitors: list[str]) -> dict:
    if not competitors:
        return {"results": [], "errors": [], "count": 0}
    queries = [COMPETITOR_QUERY.format(q=c) for c in competitors[:3]]
    return await _gather(queries, competitors[:3], "news", config.RETRIEVAL_DAYS)


# Back-compat alias (old callers / tests).
gather_signals = gather_company
