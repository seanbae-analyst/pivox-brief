"""Earnings-day market reaction (PROJECT.md L1/L2) — free daily prices via yfinance.

Descriptive event-study input ONLY: measures the stock's reaction around an earnings
call to test whether the standardized signal has information content. This is NOT a
price prediction or trading signal (§10).

`event_return` brackets the announcement with a 2-trading-day window (close just
before the call date -> close just after), which is robust to whether a company
reports pre-market or after-close (we don't track each company's exact report time).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class Reaction:
    ticker: str
    call_date: str
    date_before: str
    close_before: float
    date_after: str
    close_after: float
    event_return_pct: float   # (close_after / close_before - 1) * 100


def event_return(ticker: str, call_date: str, window_days: int = 8) -> Reaction | None:
    """Reaction return spanning the earnings call. None if data is unavailable."""
    import warnings

    warnings.filterwarnings("ignore")
    import yfinance as yf

    cd = date.fromisoformat(call_date)
    start = (cd - timedelta(days=window_days)).isoformat()
    end = (cd + timedelta(days=window_days)).isoformat()
    df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
    if df is None or df.empty or "Close" not in df:
        return None

    closes = df["Close"]
    if hasattr(closes, "columns"):           # DataFrame (multi-ticker shape)
        closes = closes[ticker] if ticker in closes.columns else closes.squeeze()
    closes = closes.dropna()

    before = closes[[d.date() < cd for d in closes.index]]
    after = closes[[d.date() > cd for d in closes.index]]
    if before.empty or after.empty:
        return None

    db, cb = before.index[-1].date().isoformat(), float(before.iloc[-1])
    da, ca = after.index[0].date().isoformat(), float(after.iloc[0])
    return Reaction(
        ticker, call_date, db, round(cb, 2), da, round(ca, 2), round((ca / cb - 1.0) * 100.0, 2)
    )
