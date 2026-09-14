# Market Research Agent

Type a company name → a tagged research report. Built around one honest rule:
**it never asserts anything recent that it can't cite.**

## The pipeline

| Stage | What it does | How it's tagged |
|------|---------------|-----------------|
| 1. Profile | Claude writes Overview / Headcount / Financials / Strategy / Products / R&D / Competitors from its **training knowledge**. Returns `UNKNOWN` instead of guessing numbers, with a confidence + as-of date. | `KNOWN · verify` |
| 2. Retrieval | Tavily searches the web, **hard-filtered to a credibility whitelist** (BBC, FT, The Hindu, The Ken, Al Jazeera, McKinsey, BCG, Bain, + peers). Several targeted queries: results, M&A, launches, press, strategy, layoffs. | — |
| 3. Insights | Claude reads **only** the retrieved snippets and extracts KPIs / M&A / launches / signals, then derives the second-order *"so what"* for each. Every signal must cite a source URL or it's dropped. | `RETRIEVED · cited` |

Why the two-stage split instead of "call the model when training runs out": the profile
step *is* the model's training knowledge — there is no separate newer brain. Fresh facts
can only come from Stage 2 (live retrieval). Stage 1 is background; Stage 3 is the
part you act on. See the note at the top of `agent/pipeline.py`.

## Setup

```bash
cd ~/Documents/market-research-agent
cp .env.example .env          # add ANTHROPIC_API_KEY and TAVILY_API_KEY
./run.sh                      # creates the venv, installs deps, starts the server
```

Open http://127.0.0.1:8077 . The UI streams live progress (Server-Sent Events),
injects the report on the same page, keeps a recent-search history (localStorage),
and offers **▶ View as slide deck** — a full-screen 6-slide viewer with SVG charts
built only from cited numbers. `run.sh` is the one-command launcher.

## The 6-step brief

| Step | Module | Corpus |
|---|---|---|
| — classify (sector + competitors) | `classify.py` | parametric |
| 1 Market & Macro (TAM, growth) | `steps.market` | sector |
| 2 Position & deep-dive | `steps.company` | company |
| 3 Forward thesis | `steps.company` | company |
| 4 Risks & red flags | `steps.company` | company |
| 5 Whitespace & recommendations | `steps.actions` | competitor |
| 6 Slide deck | `deck.build` | the brief |

Grounding: every number / risk / competitor move must cite a whitelisted
`source_url` (dropped in code otherwise); narratives, theses and recommendations
are labelled analysis. Deck charts use only already-cited numbers.

## Tuning

- **Sources**: edit `CREDIBLE_SOURCES` in `agent/config.py`. Only whitelisted
  domains ever reach the insight layer.
- **Queries**: edit `QUERY_TEMPLATES` in `agent/retrieval.py`.
- **Guardrails / reasoning style**: the prompts in `agent/profile.py` and
  `agent/insights.py` (the `$1B data centre → AI jobs` logic lives there).
- **Model**: `ANTHROPIC_MODEL` in `.env` (default `claude-opus-5`; use `claude-sonnet-5` for cheaper runs).
