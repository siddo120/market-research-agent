"""Orchestrates the 6-step strategy brief as a small DAG, emitting progress.

  classify        -> sector, competitors, overview (parametric)
  retrieve (x3)   -> company / sector / competitor corpora (concurrent)
  Step 1 market   -> TAM + macro         (sector corpus)
  Steps 2-4       -> position/thesis/risks (company corpus, one call)
  Step 5 actions  -> competitor whitespace + recommendations (competitor corpus)

`run_events` yields ("status", msg) as it goes, then ("result", report). `run`
drains it for non-streaming callers. (Step 6, the slide deck, is layered on the
report separately.)
"""
import asyncio
import time

from . import classify, retrieval, steps, deck


async def run_events(company_name: str):
    started = time.time()

    yield ("status", f"Classifying {company_name} and identifying competitors…")
    meta = await classify.classify(company_name)

    yield ("status",
           f"Sector: {meta['sector']}. Searching credible sources "
           "(company, sector, competitors)…")
    company_corpus, sector_corpus, competitor_corpus = await asyncio.gather(
        retrieval.gather_company(company_name),
        retrieval.gather_sector(meta["sector_query"]),
        retrieval.gather_competitors(meta["competitors"]),
    )

    yield ("status",
           f"Found {company_corpus['count']} company · {sector_corpus['count']} sector · "
           f"{competitor_corpus['count']} competitor sources. Analysing market & company…")
    market_res, company_res = await asyncio.gather(
        steps.market(meta["sector"], sector_corpus["results"]),
        steps.company(company_name, meta["sector"], company_corpus["results"]),
    )

    yield ("status", "Deriving competitor whitespace & recommendations…")
    company_context = (
        f"{market_res.get('headline','')} | "
        f"{company_res['position'].get('headline','')} | "
        f"{company_res['thesis'].get('headline','')}"
    )
    actions_res = await steps.actions(
        company_name, meta["sector"], meta["competitors"],
        competitor_corpus["results"], company_context,
    )

    report = {
        "company": company_name,
        "meta": meta,
        "steps": {
            "market": market_res,          # Step 1
            "position": company_res["position"],   # Step 2
            "thesis": company_res["thesis"],       # Step 3
            "risks": company_res["risks"],         # Step 4
            "actions": actions_res,        # Step 5
        },
        "sources": {
            "company": company_corpus,
            "sector": sector_corpus,
            "competitor": competitor_corpus,
        },
    }

    yield ("status", "Building the slide deck…")
    report["deck"] = await deck.build(report)   # Step 6

    report["elapsed_seconds"] = round(time.time() - started, 1)
    yield ("result", report)


async def run(company_name: str) -> dict:
    report = None
    async for kind, payload in run_events(company_name):
        if kind == "result":
            report = payload
    return report
