"""Model prices — public list prices, USD per 1M tokens (input, output).

These are ESTIMATES for budgeting, not billing truth. When a provider
reports the actual cost of a call inside its usage payload, SpendGuard
uses that figure instead and marks it as provider-reported. Models that
are neither reported nor in this table are counted by tokens and marked
UNPRICED — SpendGuard never invents a price. Users can override or add
any price from the /spendguard command (`price <model> <in> <out>`), and
can set a fallback rate for unpriced models in the config.

Table compiled from providers' public pricing pages, 2026-11-04.
"""

from __future__ import annotations

PRICES_AS_OF = "2026-11-04"

# Keys are normalized model ids (lowercase, dashes, no provider prefix).
PRICE_TABLE: dict[str, tuple[float, float]] = {
    # Anthropic
    "claude-sonnet-4-5": (3.00, 15.00),
    "claude-sonnet-4": (3.00, 15.00),
    "claude-opus-4-5": (15.00, 75.00),
    "claude-opus-4-1": (15.00, 75.00),
    "claude-opus-4": (15.00, 75.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-haiku-3-5": (0.80, 4.00),
    # OpenAI
    "gpt-5": (1.25, 10.00),
    "gpt-5-mini": (0.25, 2.00),
    "gpt-5-nano": (0.05, 0.40),
    "gpt-4-1": (2.00, 8.00),
    "gpt-4-1-mini": (0.40, 1.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "o3": (2.00, 8.00),
    "o4-mini": (1.10, 4.40),
    # Google
    "gemini-2-5-pro": (1.25, 10.00),
    "gemini-2-5-flash": (0.30, 2.50),
    "gemini-2-0-flash": (0.10, 0.40),
    # DeepSeek
    "deepseek-chat": (0.28, 0.42),
    "deepseek-reasoner": (0.28, 0.42),
    # xAI
    "grok-4": (3.00, 15.00),
    "grok-3-mini": (0.30, 0.50),
}


def normalize(model: str) -> str:
    """'Anthropic/Claude-Sonnet-4.5' -> 'claude-sonnet-4-5'."""
    m = (model or "").strip().lower()
    if "/" in m:
        m = m.rsplit("/", 1)[-1]
    return m.replace(".", "-").replace("_", "-")


def price_for(model: str, overrides: dict | None = None) -> tuple[tuple[float, float], str] | None:
    """Look up (input, output) USD per 1M tokens for a model.

    Exact match first (user overrides win), then the longest table key
    that prefixes the model id, so dated snapshots like
    'claude-sonnet-4-5-20250929' still price as 'claude-sonnet-4-5'.
    Returns ((in, out), source) or None when unpriced.
    """
    norm = normalize(model)
    if not norm:
        return None
    for source, table in (("override", overrides or {}), ("table", PRICE_TABLE)):
        norm_table = {normalize(k): v for k, v in table.items()}
        if norm in norm_table:
            return norm_table[norm], source
        best = None
        for key, val in norm_table.items():
            if norm.startswith(key + "-") or norm == key:
                if best is None or len(key) > len(best[0]):
                    best = (key, val)
        if best is not None:
            return best[1], source
    return None


def provider_cost(usage: dict | None) -> float | None:
    """Actual cost reported by the provider inside the usage payload."""
    if not usage:
        return None
    for key in ("cost", "total_cost", "cost_usd", "totalCost"):
        val = usage.get(key)
        if isinstance(val, (int, float)) and val >= 0:
            return float(val)
    return None


def token_counts(usage: dict | None) -> tuple[int, int]:
    """(input_tokens, output_tokens) from either provider's usage shape."""
    if not usage:
        return 0, 0
    inp = usage.get("prompt_tokens", usage.get("input_tokens", 0))
    out = usage.get("completion_tokens", usage.get("output_tokens", 0))
    try:
        return int(inp or 0), int(out or 0)
    except (TypeError, ValueError):
        return 0, 0


def estimate(model: str, input_tokens: int, output_tokens: int,
             overrides: dict | None = None,
             fallback: tuple[float, float] | None = None) -> tuple[float | None, str]:
    """Estimated USD cost of one call. (None, 'unpriced') when unknown."""
    found = price_for(model, overrides)
    if found is not None:
        (rate_in, rate_out), source = found
        return (input_tokens * rate_in + output_tokens * rate_out) / 1_000_000.0, source
    if fallback is not None:
        rate_in, rate_out = fallback
        return (input_tokens * rate_in + output_tokens * rate_out) / 1_000_000.0, "fallback"
    return None, "unpriced"
