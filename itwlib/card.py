"""Pure logic for the share card: brand colors + the site's exact STRENGTH / TOP%
formulas (reverse-engineered from the bundle). No rendering, no network — testable.
"""
from __future__ import annotations

# card palette (from CSS custom properties)
BG = "#181a44"          # --terminal-card-background
FG = "#f2f2f2"          # default text / rule
ACCENT = "#ffe422"      # .terminal-result-stats (STRENGTH · TOP%)
SNIPPET = "#b9b9c9"     # ~ #f2f2f2 @ 66% alpha over navy (.result-snippet)
TRACK = "#2a2c55"       # unfilled bar track (slightly above bg)

# per-model bar colors — object `Gn` in the bundle. Two ids are absent and use
# the hashed-HSL fallback below (matches the site exactly).
BRAND_COLORS = {
    "openai/gpt-5.5": "#f2f2f2",
    "anthropic/claude-opus-4.8": "#d27967",
    "x-ai/grok-4.20": "#555555",
    "google/gemini-3.1-flash-lite": "#4f7bec",
    "moonshotai/kimi-k2-0905": "#1f9e8a",
    "deepseek/deepseek-v4-flash": "#4d6bfe",
    "meta-llama/llama-3.3-70b-instruct": "#0866ff",
    "z-ai/glm-4.7-flash": "#e05c9a",
    "mistralai/mistral-small-3.2-24b-instruct": "#e6aa35",
    "qwen/qwen3-8b": "#6235d8",
    "meta-llama/llama-3.2-1b-instruct": "#2256bc",
}


def _hsl_to_hex(h: float, s: float, l: float) -> str:
    """h in [0,360), s/l in [0,1] -> #rrggbb."""
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l - c / 2
    r, g, b = {
        0: (c, x, 0), 1: (x, c, 0), 2: (0, c, x),
        3: (0, x, c), 4: (x, 0, c), 5: (c, 0, x),
    }[int(h // 60) % 6]
    return "#%02x%02x%02x" % (round((r + m) * 255), round((g + m) * 255), round((b + m) * 255))


def brand_color(model_id: str) -> str:
    """Bar color for a model id; hashed-HSL fallback for ids not in BRAND_COLORS
    (mirrors the bundle's `Tr()`: t=(t*31+ord(ch))%360, then hsl(t,72%,48%))."""
    if model_id in BRAND_COLORS:
        return BRAND_COLORS[model_id]
    t = 0
    for ch in model_id:
        t = (t * 31 + ord(ch)) % 360
    return _hsl_to_hex(t, 0.72, 0.48)


def _clamp_score(v) -> float:
    try:
        return max(0.0, min(100.0, float(v)))
    except (TypeError, ValueError):
        return 0.0


def strength(referent: dict, models: list[dict]) -> int:
    """Reproduce the bundle's `kr()`: 0–1000 score.
    round( meanRecognition/100 * 800  +  (200/len(models)) * coverageCount )
      meanRecognition = mean over all models of recognitionScore (ok cells only)
      coverageCount   = # models whose cell is ok AND confidence > 0
    """
    n = len(models)
    if n <= 0:
        return 0
    cells = referent.get("cells") or {}
    total_recog = 0.0
    coverage = 0
    for m in models:
        c = cells.get(m.get("id")) or {}
        ok = c.get("status") == "ok"
        if ok:
            total_recog += _clamp_score(c.get("recognitionScore", 0))
            if (c.get("confidence") or 0) > 0:
                coverage += 1
    mean = total_recog / n
    bonus = (1000 - 800) / n * coverage
    return round(mean / 100 * 800 + bonus)


def top_pct(rank, total) -> str | None:
    """Reproduce the bundle's `pt(rank,total)`."""
    if not total or total <= 0:
        return None
    n = (rank - 1) / total * 100
    r = max(1, round(n))
    if r <= 10:
        return f"Top {r}%"
    return f"Top {min(95, round(n / 5) * 5)}%"


def bar_fill_pct(confidence) -> int:
    """Bar length = confidence snapped to nearest 10% (bundle's `Rr`)."""
    return round(_clamp_score(confidence) / 10) * 10
