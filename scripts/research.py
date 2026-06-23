"""Build a one-page research pack for a US ticker / company name (step 5).

    python scripts/research.py NVDA
    python scripts/research.py "advanced micro devices"
    python scripts/research.py AAPL --save        # also writes data/output/AAPL.research.md

US issuers resolve via SEC EDGAR (keyless; set EDGAR_USER_AGENT in .env to declare
identity). KR issuers route to the DART path (engine/dart.py) once DART_API_KEY is
set — not yet wired here.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.research_pack import build_us_pack, render_markdown  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="One-page research pack (US / SEC EDGAR).")
    ap.add_argument("query", help="ticker or company name, e.g. NVDA or 'nvidia'")
    ap.add_argument("--no-price", action="store_true", help="skip the demo price snapshot (no yfinance call)")
    ap.add_argument("--save", action="store_true", help="write data/output/<TICKER>.research.md")
    args = ap.parse_args(argv)

    pack = build_us_pack(args.query, with_price=not args.no_price)
    if pack is None:
        print(
            f"'{args.query}' did not resolve in SEC EDGAR (US issuers). "
            "KR issuers need the DART path (set DART_API_KEY) — not yet wired.",
            file=sys.stderr,
        )
        return 2

    md = render_markdown(pack)
    print(md)

    if args.save:
        ticker = pack.profile.tickers[0] if pack.profile.tickers else args.query.upper()
        out = ROOT / "data" / "output" / f"{ticker}.research.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md + "\n", encoding="utf-8")
        print(f"\n[saved] {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
