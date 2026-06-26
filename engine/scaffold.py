"""Research scaffold — Wave-3 capstone (STRATEGY.md, the "where to look" layer).

Synthesizes the already-assembled pack (qualitative themes, quality flags, risk-factor delta,
insider pattern, peer position) into a **research agenda**: the handful of things that will move
this stock, the data point on each, and the OPEN QUESTION you need to resolve. It poses questions;
it never answers them — descriptive, not advice (§10). The whole point is "so you can research."

Pure function over the structured record (no new fetching), so it unit-tests offline and adds no
latency. It re-presents signals the pack already carries as a prioritized, source-linked agenda.
"""

from __future__ import annotations

from typing import Optional

# What to ask when a given signal shows up. Each is a research PROMPT (a question), never a verdict.
_THEME_Q = {
    "demand_strength": "Is the demand durable, or cycle-driven? Cross-check customer capex / end-market guidance.",
    "demand_weakness": "Is the softness cyclical or structural (share loss)? Compare to peers' trajectories.",
    "capex_investment": "Will the investment earn its cost of capital, and over what horizon?",
    "margin_expansion": "Is the margin gain mix / one-off, or a sustainable structural step-up?",
    "margin_pressure": "Is the pressure transient (input costs) or structural (pricing / competition)?",
    "pricing_power": "How durable is pricing power if demand softens?",
    "competitive_pressure": "How defensible is the position vs the named competitors?",
    "supply_constraint": "Is supply the binding constraint, and when does it ease?",
    "new_product_ramp": "Does the ramp carry the next year's growth, and what's the execution risk?",
    "market_share_gain": "Is the share gain price-led or product-led — and is it sticky?",
    "regulatory_legal": "How material and quantified is the regulatory / legal exposure?",
    "macro_headwind": "How sensitive are results to the macro factor, and is it priced in?",
    "capital_return": "Is the capital return sustainable from FCF, or balance-sheet-funded?",
    "segment_expansion": "Is the new segment accretive to margins, or dilutive while it scales?",
    "cost_efficiency": "Are the cost savings structural or one-time?",
    "m_and_a": "What's the integration risk and the multiple paid?",
}

_FLAG_Q = {
    "accrual_gap": "Is net income running ahead of cash a growth working-capital build, or recognition quality?",
    "cash_conversion": "Why is cash conversion where it is — capex cycle, working capital, or quality?",
    "fcf_conversion": "Is the FCF-to-earnings gap explained by capex intensity?",
    "net_margin_trend": "Is the margin trajectory mix-driven or durable?",
    "rev_growth_trend": "Is the growth-rate trajectory base-effect or a real inflection?",
    "share_count_change": "What's driving the share-count change — buybacks, comp, raises, or M&A?",
    "net_loss": "What's the path to profitability, and is cash runway adequate?",
}


def _short(text: str, n: int = 90) -> str:
    text = (text or "").strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def build_scaffold(record: dict, max_items: int = 7) -> Optional[dict]:
    """Build the research agenda from a structured record (to_record / to_page_dict shape).
    Returns None if the record carries no usable signal."""
    items: list[dict] = []

    # Agenda order interleaves areas so the distinctive *events* (new risk, insider) aren't
    # crowded out of the cap by a long theme/quality list.

    # 1) Core drivers from the filings-derived themes (capped to leave room for events).
    qual = record.get("qualitative") or {}
    for t in (qual.get("themes") or [])[:3]:
        theme = t.get("theme")
        q = _THEME_Q.get(theme)
        if not q:
            continue
        arrow = {"positive": "▲", "negative": "▼", "neutral": "•"}.get(t.get("direction"), "•")
        items.append({
            "area": "Demand / narrative",
            "signal": f"{arrow} {theme}: {_short(t.get('evidence', ''))}",
            "question": q,
            "source_url": t.get("source_url"),
        })

    # 2) Newly-disclosed risk (the Δ-time event — high distinctiveness, so before 2nd-tier quality).
    rd = record.get("risk_delta") or {}
    for added in (rd.get("added") or [])[:1]:
        items.append({
            "area": "New risk (10-K YoY)",
            "signal": f"Newly disclosed: {_short(added, 110)}",
            "question": "How material is this newly-added risk, and why now?",
            "source_url": (rd.get("current_filing") or {}).get("url"),
        })

    # 3) Insider behavior (behavioral event).
    ip = (record.get("ownership") or {}).get("insider_pattern") or {}
    buys, sells = ip.get("open_market_buys", 0), ip.get("open_market_sells", 0)
    if ip.get("cluster_buy") and buys:
        items.append({"area": "Insider behavior",
                      "signal": _short(ip.get("observation", "")),
                      "question": "Multiple insiders buying — conviction signal? Check the sizes and prices."})
    elif sells and ip.get("sell_value", 0) > max(ip.get("buy_value", 0) * 2, 0):
        items.append({"area": "Insider behavior",
                      "signal": _short(ip.get("observation", "")),
                      "question": "Is the insider selling distribution, or routine 10b5-1 diversification?"})

    # 4) Earnings-quality questions.
    for f in (record.get("quality_flags") or [])[:2]:
        q = _FLAG_Q.get(f.get("key"))
        if not q:
            continue
        items.append({"area": "Earnings quality", "signal": _short(f.get("observation", "")), "question": q})

    # 5) Peer-relative outliers (best / worst on a factor).
    for f in ((record.get("peers") or {}).get("factors") or []):
        rank, n = f.get("rank"), f.get("n")
        if rank in (1, n) and n and n >= 3:
            where = "highest" if rank == 1 else "lowest"
            items.append({
                "area": "Peer position",
                "signal": f"{f.get('label')} {f.get('value')}% — {where} of {n} peers",
                "question": f"Is the peer-extreme {f.get('label', '').lower()} structural, or cyclical vs peers?",
            })

    if not items:
        return None
    return {
        "items": items[:max_items],
        "note": "A research agenda — the signals above re-framed as what to watch and what to resolve. "
                "Descriptive prompts, not answers or advice (§10).",
    }
