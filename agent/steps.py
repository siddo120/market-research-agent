"""The analysis steps of the 6-step strategy brief (Steps 1-5).

Each step reasons over a retrieved corpus and returns a normalized dict. The
grounding contract is the same everywhere:
- Any number / hard fact must cite a `source_url` taken from the provided
  material; uncited data points are dropped in code (`_cited`).
- The narrative / thesis / recommendation IS the model's analysis — allowed
  without a citation, but it must be grounded in the cited facts, never invented.

To keep latency/cost down, Steps 2-4 (position, forward thesis, risks) share one
call over the company corpus; Steps 1 and 5 have their own corpora.
"""
from . import llm


def _format(results: list[dict]) -> str:
    """Compact retrieval hits into a numbered block for the model."""
    if not results:
        return "(no material retrieved)"
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(
            f"[{i}] {r['source']} | {r['url']} | {r.get('published_date') or 'n/a'}\n"
            f"{r['title']}\n{r['content']}"
        )
    return "\n\n".join(lines)


NO_BRACKETS = (" Do not put bracketed source markers like [3] or [12] in any "
               "narrative/headline text — the data points carry the real links.")


def _cited(items, urls: set[str], key: str = "source_url"):
    """Keep only items whose source_url is one of the provided (whitelisted) URLs."""
    out = []
    for it in items or []:
        if isinstance(it, dict) and it.get(key) in urls:
            out.append(it)
    return out


# ── Step 1 — Market & Macro ────────────────────────────────────────────────
MARKET_SYS = """You are a market strategist. From the retrieved material about a \
SECTOR, summarise the total addressable market and macro growth.

Rules: every number (market size, CAGR, growth %) MUST cite a source_url from the \
material. If a figure isn't in the material, do not state it. The "narrative" is \
your macro read of where the sector is heading — analysis, grounded in the facts.

JSON: {
 "headline": "one-line macro takeaway",
 "narrative": "2-4 sentences on sector direction, tailwinds/headwinds",
 "data_points": [{"label":"e.g. Market size 2025","value":"$X bn","insight":"why it matters","source":"publisher","source_url":"https://...","as_of":"year"}],
 "note": "caveat if the material is thin"
}"""


async def market(sector: str, corpus: list[dict]) -> dict:
    urls = {r["url"] for r in corpus}
    user = f"Sector: {sector}\n\nMaterial:\n{_format(corpus)}\n\nAnalyse now."
    d = await llm.chat_json(MARKET_SYS + NO_BRACKETS, user)
    return {
        "headline": d.get("headline", ""),
        "narrative": d.get("narrative", ""),
        "data_points": _cited(d.get("data_points"), urls),
        "note": d.get("note", ""),
    }


# ── Steps 2-4 — Position, Forward thesis, Risks (one call, company corpus) ──
COMPANY_SYS = """You are a company strategist analysing ONE company from retrieved \
news. Work only from the material; cite every number with a source_url from it. \
Narratives are your analysis, grounded in the cited facts — never invent figures.

Produce three linked sections:
- position: current standing — revenue, profit, market share, and which vertical \
the company has been deep-diving into (from its releases/acquisitions/launches).
- thesis: where it's headed next. Read recent deals/launches as directional \
signals and say what vertical it's betting on and why (connect two facts into a \
thesis, e.g. an audio firm + an AI-voice deal => faster AI-narrated production).
- risks: red flags — lawsuits, layoffs, shutdowns, negative press, misconduct — \
each with why it matters (e.g. a product shutdown => that R&D bet didn't scale).

JSON: {
 "position": {"headline":"", "narrative":"", "data_points":[{"label":"","value":"","insight":"","source":"","source_url":"","as_of":""}]},
 "thesis":   {"headline":"", "narrative":"", "data_points":[{"label":"signal","value":"the move","insight":"what it implies","source":"","source_url":"","as_of":""}]},
 "risks":    {"headline":"", "flags":[{"risk":"","why":"","severity":"high|medium|low","source":"","source_url":"","as_of":""}], "note":""}
}"""


async def company(name: str, sector: str, corpus: list[dict]) -> dict:
    urls = {r["url"] for r in corpus}
    user = (f"Company: {name}\nSector: {sector}\n\nMaterial:\n{_format(corpus)}\n\n"
            "Produce position, thesis, and risks now.")
    d = await llm.chat_json(COMPANY_SYS + NO_BRACKETS, user)
    pos = d.get("position") or {}
    th = d.get("thesis") or {}
    rk = d.get("risks") or {}
    return {
        "position": {
            "headline": pos.get("headline", ""), "narrative": pos.get("narrative", ""),
            "data_points": _cited(pos.get("data_points"), urls),
        },
        "thesis": {
            "headline": th.get("headline", ""), "narrative": th.get("narrative", ""),
            "data_points": _cited(th.get("data_points"), urls),
        },
        "risks": {
            "headline": rk.get("headline", ""),
            "flags": _cited(rk.get("flags"), urls),
            "note": rk.get("note", ""),
        },
    }


# ── Step 5 — Competitor whitespace & recommendations ───────────────────────
ACTIONS_SYS = """You are a strategy advisor. Given a company, its sector, and \
retrieved news about its COMPETITORS, do two things:
1. competitor_moves: summarise what rivals are doing (cite each with a source_url \
from the material).
2. recommendations: 2-4 concrete strategic plays THIS company should make — where \
is the whitespace, which vertical to enter, what product strategy. Ground each in \
the competitor signal or the company's position; recommendations are your analysis \
(no citation needed) but must be specific, not generic.

JSON: {
 "headline": "one-line strategic takeaway",
 "narrative": "2-3 sentences framing the competitive landscape",
 "competitor_moves": [{"competitor":"","move":"","implication":"","source":"","source_url":"","as_of":""}],
 "recommendations": [{"move":"the play","rationale":"why now / based on what","target_vertical":""}],
 "note": ""
}"""


async def actions(name: str, sector: str, competitors: list[str],
                  corpus: list[dict], company_context: str) -> dict:
    urls = {r["url"] for r in corpus}
    user = (f"Company: {name}\nSector: {sector}\n"
            f"Competitors: {', '.join(competitors) or 'unknown'}\n"
            f"Company context: {company_context}\n\n"
            f"Competitor material:\n{_format(corpus)}\n\nAdvise now.")
    d = await llm.chat_json(ACTIONS_SYS + NO_BRACKETS, user)
    recs = [r for r in (d.get("recommendations") or []) if isinstance(r, dict)]
    return {
        "headline": d.get("headline", ""),
        "narrative": d.get("narrative", ""),
        "competitor_moves": _cited(d.get("competitor_moves"), urls),
        "recommendations": recs,
        "note": d.get("note", ""),
    }
