"""Central config: settings + the credibility whitelist.

The whitelist is the heart of the "only trust high-credibility sources" rule.
Edit CREDIBLE_SOURCES freely — the retrieval layer will only accept results
whose domain matches one of these entries.
"""
import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-5")
# Reasoning depth: low | medium | high | xhigh | max. "low" keeps this
# structured-extraction task fast + cheap; raise it if you want deeper insights.
ANTHROPIC_EFFORT = os.getenv("ANTHROPIC_EFFORT", "low")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
MAX_RESULTS_PER_QUERY = int(os.getenv("MAX_RESULTS_PER_QUERY", "6"))
# Recency window for retrieval (days). Default ~6 years (2020-2026 per the brief);
# results are still recency-ranked, so fresh news beats stale coverage.
RETRIEVAL_DAYS = int(os.getenv("RETRIEVAL_DAYS", "2190"))

# Domain -> human-readable label.
# Core list is exactly what you named; the second block adds a few obvious
# peers (wire-service + establishment press + top think tanks). Prune/add at will.
CREDIBLE_SOURCES: dict[str, str] = {
    # --- Your named list ---
    "bbc.com": "BBC",
    "bbc.co.uk": "BBC",
    "thehindu.com": "The Hindu",
    "newyorker.com": "The New Yorker",
    "ft.com": "Financial Times",
    "the-ken.com": "The Ken",
    "aljazeera.com": "Al Jazeera",
    "bcg.com": "BCG",
    "mckinsey.com": "McKinsey",
    "bain.com": "Bain",
    # --- Established Indian business press (same tier as The Hindu) ---
    # These cover Indian companies/startups the global-prestige press ignores.
    "economictimes.indiatimes.com": "The Economic Times",
    "moneycontrol.com": "Moneycontrol",
    "livemint.com": "Mint",
    "business-standard.com": "Business Standard",
    # --- Peer high-credibility sources (edit freely) ---
    "reuters.com": "Reuters",
    "apnews.com": "Associated Press",
    "economist.com": "The Economist",
    "bloomberg.com": "Bloomberg",
    "wsj.com": "Wall Street Journal",
    "nytimes.com": "The New York Times",
    "theguardian.com": "The Guardian",
    "nikkei.com": "Nikkei",
    "brookings.edu": "Brookings",
    "hbr.org": "Harvard Business Review",
}

# Convenience list for the Tavily include_domains parameter.
WHITELIST_DOMAINS = sorted(set(CREDIBLE_SOURCES.keys()))


def source_label(url: str) -> str | None:
    """Return the credible-source label for a URL, or None if not whitelisted."""
    url = (url or "").lower()
    for domain, label in CREDIBLE_SOURCES.items():
        if domain in url:
            return label
    return None


def _is_unset(value: str) -> bool:
    """True if a key is blank or still the .env.example placeholder (ends '...')."""
    value = (value or "").strip()
    return value == "" or value.endswith("...")


def missing_keys() -> list[str]:
    """Which required API keys are absent or still placeholders — warned on the UI."""
    missing = []
    if _is_unset(ANTHROPIC_API_KEY):
        missing.append("ANTHROPIC_API_KEY")
    if _is_unset(TAVILY_API_KEY):
        missing.append("TAVILY_API_KEY")
    return missing
