"""Step 6 — turn the finished 5-step brief into a slide-deck spec.

Charts are built ONLY from numbers already cited in the brief: the model parses
the cited data-point values into numeric series and copies the source_url they
came from. Any chart whose source_url isn't one of the brief's cited URLs is
dropped in code, so nothing on a slide is uncited or invented. Slides with no
citable numbers fall back to bullets (per the "omit uncited charts" decision).

Output is a JSON spec; the deck itself is rendered client-side (SVG) in the UI.
"""
from . import llm

SYSTEM = """You are a management consultant building a concise 6-slide strategy \
deck from a research brief. Slide 1 is a summary; slides 2-6 map to the five \
analysis steps (Market & Macro, Position, Forward Thesis, Risks, Recommendations).

CHART RULES (strict):
- You may ONLY use numbers that appear in the provided data points. Never invent, \
round-trip, or estimate a figure.
- Every chart MUST copy the source_url of the data point(s) it draws from.
- Parse figures to numeric: "$500M" -> value 500, unit "$M"; "₹1,052 crore" -> \
value 1052, unit "₹ cr"; "350m users" -> value 350, unit "m".
- Chart types: "line"/"bar" for a series of >=2 cited numbers (e.g. ARR over \
time); "pie" for a cited share split (>=2 segments); "metric" for a single cited \
figure. If a slide has no citable numbers, use bullets only and "charts": [].
- 2-4 crisp bullets per slide.

Return JSON:
{
 "title": "<Company> — Strategy Brief",
 "subtitle": "one-line strategic thesis",
 "slides": [
   {"step":"Summary","headline":"","bullets":["",""],
    "charts":[{"type":"metric","title":"ARR","value":"$500M","unit":"","source":"","source_url":""}]},
   {"step":"Market & Macro","headline":"","bullets":[],
    "charts":[{"type":"line","title":"","unit":"$M","data":[{"label":"FY24","value":0}],"source":"","source_url":""}]}
 ]
}
Slides array must have exactly 6 entries in that order."""


def _report_urls(report: dict) -> set[str]:
    urls: set[str] = set()
    for step in report["steps"].values():
        for key in ("data_points", "flags", "competitor_moves"):
            for it in step.get(key, []) or []:
                if it.get("source_url"):
                    urls.add(it["source_url"])
    return urls


def _summarize(report: dict) -> str:
    """Compact the brief (headlines, narratives, cited data points) for the model."""
    s = report["steps"]
    lines = [f"COMPANY: {report['company']}",
             f"SECTOR: {report['meta'].get('sector','')}",
             f"OVERVIEW: {report['meta'].get('overview','')}", ""]

    def dump_points(title, items, valuey=True):
        lines.append(title + ":")
        for it in items or []:
            if valuey:
                lines.append(f"  - {it.get('label','')}: {it.get('value','')} "
                             f"| {it.get('insight','')} | src={it.get('source_url','')}")
            else:
                lines.append(f"  - {it}")

    lines.append(f"[1 MARKET] {s['market'].get('headline','')}\n{s['market'].get('narrative','')}")
    dump_points("market data", s["market"].get("data_points"))
    lines.append(f"\n[2 POSITION] {s['position'].get('headline','')}\n{s['position'].get('narrative','')}")
    dump_points("position data", s["position"].get("data_points"))
    lines.append(f"\n[3 THESIS] {s['thesis'].get('headline','')}\n{s['thesis'].get('narrative','')}")
    dump_points("thesis signals", s["thesis"].get("data_points"))
    lines.append(f"\n[4 RISKS] {s['risks'].get('headline','')}")
    for it in s["risks"].get("flags", []) or []:
        lines.append(f"  - [{it.get('severity','')}] {it.get('risk','')} — {it.get('why','')} | src={it.get('source_url','')}")
    lines.append(f"\n[5 RECOMMENDATIONS] {s['actions'].get('headline','')}\n{s['actions'].get('narrative','')}")
    for it in s["actions"].get("recommendations", []) or []:
        lines.append(f"  - {it.get('move','')} (target: {it.get('target_vertical','')}) — {it.get('rationale','')}")
    return "\n".join(lines)


def _clean_charts(charts, valid_urls: set[str]) -> list:
    out = []
    for c in charts or []:
        if not isinstance(c, dict):
            continue
        if c.get("source_url") not in valid_urls:
            continue  # every chart must trace to a cited source
        ctype = c.get("type")
        if ctype in ("line", "bar", "pie"):
            data = [d for d in (c.get("data") or [])
                    if isinstance(d, dict) and isinstance(d.get("value"), (int, float))]
            if len(data) < 2:
                continue  # not enough real numbers to plot
            c["data"] = data
        elif ctype == "metric":
            if not c.get("value"):
                continue
        else:
            continue
        out.append(c)
    return out


async def build(report: dict) -> dict:
    valid_urls = _report_urls(report)
    user = _summarize(report) + "\n\nBuild the 6-slide deck now."
    d = await llm.chat_json(SYSTEM, user)

    slides = []
    for sl in (d.get("slides") or [])[:6]:
        if not isinstance(sl, dict):
            continue
        slides.append({
            "step": sl.get("step", ""),
            "headline": sl.get("headline", ""),
            "bullets": [b for b in (sl.get("bullets") or []) if isinstance(b, str)][:4],
            "charts": _clean_charts(sl.get("charts"), valid_urls),
        })
    return {
        "title": d.get("title") or f"{report['company']} — Strategy Brief",
        "subtitle": d.get("subtitle", ""),
        "slides": slides,
    }
