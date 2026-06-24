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
from typing import Optional


@dataclass
class LatestClose:
    ticker: str
    date: str
    close: float


def latest_close(ticker: str, lookback_days: int = 10) -> Optional[LatestClose]:
    """Most recent daily close (demo-labeled, isolated — DATA_SOURCES.md §5).

    yfinance is ToS-gray and used here for a personal/demo snapshot only; a public
    or commercial build must swap in a licensed feed. None if data is unavailable.
    """
    import warnings

    warnings.filterwarnings("ignore")
    import yfinance as yf

    end = date.today() + timedelta(days=1)
    start = end - timedelta(days=lookback_days)
    df = yf.download(ticker, start=start.isoformat(), end=end.isoformat(),
                     progress=False, auto_adjust=True)
    if df is None or df.empty or "Close" not in df:
        return None
    closes = df["Close"]
    if hasattr(closes, "columns"):
        closes = closes[ticker] if ticker in closes.columns else closes.squeeze()
    closes = closes.dropna()
    if closes.empty:
        return None
    return LatestClose(ticker, closes.index[-1].date().isoformat(), round(float(closes.iloc[-1]), 2))


@dataclass
class Technicals:
    """Demo-labeled price-action snapshot (DATA_SOURCES.md §5 — gray/personal only)."""

    as_of: str
    last_close: float
    ret_1m_pct: Optional[float] = None
    ret_ytd_pct: Optional[float] = None
    ret_1y_pct: Optional[float] = None
    high_52w: Optional[float] = None
    low_52w: Optional[float] = None
    pct_from_52w_high: Optional[float] = None
    ma50: Optional[float] = None
    ma200: Optional[float] = None


def _close_series(ticker: str, lookback_days: int):
    """Clean daily-close pandas Series (demo source), or None. Shared shape-handling
    with latest_close: yfinance returns a multi-index frame for some tickers."""
    import warnings

    warnings.filterwarnings("ignore")
    import yfinance as yf

    end = date.today() + timedelta(days=1)
    start = end - timedelta(days=lookback_days)
    df = yf.download(ticker, start=start.isoformat(), end=end.isoformat(),
                     progress=False, auto_adjust=True)
    if df is None or df.empty or "Close" not in df:
        return None
    closes = df["Close"]
    if hasattr(closes, "columns"):
        closes = closes[ticker] if ticker in closes.columns else closes.squeeze()
    closes = closes.dropna()
    return closes if not closes.empty else None


def _ret_from(closes, days: int) -> Optional[float]:
    """Pct return of the last close vs the close nearest `days` calendar days earlier."""
    last_dt = closes.index[-1]
    target = last_dt - timedelta(days=days)
    prior = closes[closes.index <= target]
    if prior.empty:
        return None
    return round((float(closes.iloc[-1]) / float(prior.iloc[-1]) - 1.0) * 100.0, 1)


def technicals(ticker: str, lookback_days: int = 430) -> Optional[Technicals]:
    """~14-month price-action snapshot: trailing returns, 52-week range, 50/200-day MAs.

    Demo-labeled (yfinance, DATA_SOURCES.md §5); a public/commercial build swaps in a
    licensed feed. None if price data is unavailable — never blocks the pack.
    """
    closes = _close_series(ticker, lookback_days)
    if closes is None:
        return None

    last_close = round(float(closes.iloc[-1]), 2)
    as_of = closes.index[-1].date().isoformat()

    # 52-week window (~365 calendar days back from the latest close).
    yr = closes[closes.index >= (closes.index[-1] - timedelta(days=365))]
    high_52w = round(float(yr.max()), 2) if not yr.empty else None
    low_52w = round(float(yr.min()), 2) if not yr.empty else None
    pct_from_high = round((last_close / high_52w - 1.0) * 100.0, 1) if high_52w else None

    # Year-to-date: first close on/after Jan 1 of the latest close's year.
    jan1 = date(closes.index[-1].year, 1, 1)
    ytd_slice = closes[[d.date() >= jan1 for d in closes.index]]
    ret_ytd = (round((last_close / float(ytd_slice.iloc[0]) - 1.0) * 100.0, 1)
               if not ytd_slice.empty else None)

    ma50 = round(float(closes.iloc[-50:].mean()), 2) if len(closes) >= 50 else None
    ma200 = round(float(closes.iloc[-200:].mean()), 2) if len(closes) >= 200 else None

    return Technicals(
        as_of=as_of,
        last_close=last_close,
        ret_1m_pct=_ret_from(closes, 30),
        ret_ytd_pct=ret_ytd,
        ret_1y_pct=_ret_from(closes, 365),
        high_52w=high_52w,
        low_52w=low_52w,
        pct_from_52w_high=pct_from_high,
        ma50=ma50,
        ma200=ma200,
    )


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
