"""Periodic, event-driven refresh of the research packs for a watchlist.

Cheap poll → rebuild only what changed:
  1. Poll each ticker's EDGAR submissions (ONE request) for its latest filing of any type.
  2. Compare to last-run state (data/refresh_state.json); a newer filing = an event.
  3. Rebuild the research record for changed (or --all) tickers; write JSON; stamp last_event.
  4. Print a "what changed since last run" diff and update state.

Scheduler-agnostic — run from local cron/launchd (freshest for $0; see DATA_SOURCES.md). The
poll is one request per ticker, so frequent runs are cheap; the expensive rebuild only fires
on a new filing. Watchlist = CLI args, else data/watchlist.txt, else existing data/output packs.

    python scripts/refresh.py NVDA AAPL AMD     # poll; rebuild only what changed
    python scripts/refresh.py --all             # force-rebuild the whole watchlist
    python scripts/refresh.py --poll-only       # detect changes, don't rebuild (no state write)

Note: a rebuild refreshes quant / filings / ownership / news automatically, and RELOADS the
cached qualitative block — it does not re-extract it. When a new 10-Q/10-K/earnings 8-K drops,
the diff flags that qualitative re-extraction (the $0 in-session or API path) is due.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

from engine import edgar  # noqa: E402
from engine.research_pack import build_us_pack, to_record  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "output"
STATE = ROOT / "data" / "refresh_state.json"
QUAL_FORMS = {"10-Q", "10-K", "8-K"}  # forms whose arrival makes the qualitative block stale


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def poll_latest(query: str):
    """Most recent filing of ANY type for a ticker (one request). (ticker, cik, filing|None)."""
    ref = edgar.resolve_ticker(query)
    if ref is None:
        return query.upper(), None, None
    _, filings = edgar.company_filings(ref.cik, forms=None, limit=1)
    return ref.ticker, ref.cik, (filings[0] if filings else None)


def watchlist(args_tickers) -> list[str]:
    if args_tickers:
        return [t.upper() for t in args_tickers]
    wl = ROOT / "data" / "watchlist.txt"
    if wl.exists():
        return [ln.strip().upper() for ln in wl.read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.startswith("#")]
    return sorted(p.name[: -len(".research.json")] for p in OUT.glob("*.research.json"))


def main(argv=None) -> int:
    load_dotenv(str(ROOT / ".env"))
    ap = argparse.ArgumentParser(description="Event-driven research-pack refresh.")
    ap.add_argument("tickers", nargs="*", help="tickers (default: data/watchlist.txt or existing packs)")
    ap.add_argument("--all", action="store_true", help="rebuild every ticker regardless of changes")
    ap.add_argument("--poll-only", action="store_true", help="detect changes; do not rebuild or write state")
    args = ap.parse_args(argv)

    wl = watchlist(args.tickers)
    if not wl:
        print("no watchlist — pass tickers, add data/watchlist.txt, or build a pack first", file=sys.stderr)
        return 1

    state = load_state()
    print(f"[refresh {_now()}] {len(wl)} ticker(s): {', '.join(wl)}")
    changed, rebuilt = [], []

    for q in wl:
        ticker, cik, latest = poll_latest(q)
        if cik is None:
            print(f"  {q:8s} — did not resolve (US / EDGAR)")
            continue

        prev = state.get(ticker, {})
        acc = latest.accession if latest else None
        tag = f"{latest.form} {latest.filing_date}" if latest else "—"
        is_new = acc is not None and acc != prev.get("latest_accession")

        if is_new:
            changed.append(ticker)
            where = f" (was {prev.get('latest_form')} {prev.get('latest_date')})" if prev else " (first seen)"
            print(f"  {ticker:8s} ★ NEW: {tag}{where}")
            if latest.form in QUAL_FORMS:
                print(f"           → qualitative re-extraction due (new {latest.form})")
        else:
            print(f"  {ticker:8s} — unchanged ({tag})")

        if (is_new or args.all) and not args.poll_only:
            try:
                rec = to_record(build_us_pack(ticker))
                OUT.mkdir(parents=True, exist_ok=True)
                (OUT / f"{ticker}.research.json").write_text(
                    json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                rebuilt.append(ticker)
                le = rec.get("last_event") or {}
                print(f"           [rebuilt] last_event = {le.get('form')} {le.get('filed')}")
            except Exception as exc:
                print(f"           [rebuild failed] {exc}")

        if latest and not args.poll_only:
            state[ticker] = {
                "latest_accession": acc, "latest_form": latest.form, "latest_date": latest.filing_date,
                "polled_at": _now(),
                "refreshed_at": _now() if ticker in rebuilt else prev.get("refreshed_at"),
            }

    if not args.poll_only:
        save_state(state)
    print(f"[done] {len(changed)} changed, {len(rebuilt)} rebuilt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
