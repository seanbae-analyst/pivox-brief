"""Build a one-page research pack for a ticker / company name (steps 5 + KR routing).

    python scripts/research.py NVDA
    python scripts/research.py "advanced micro devices"
    python scripts/research.py 삼성전자 --save        # KR via DART (needs DART_API_KEY)

US issuers resolve via SEC EDGAR (keyless; set EDGAR_USER_AGENT in .env). If the
query doesn't resolve in EDGAR, it routes to the Korean path via Open DART
(engine/dart.py), which needs a free DART_API_KEY in .env — KR stock in Korean.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402
from engine.research_pack import build_us_pack, render_markdown  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    load_dotenv()  # EDGAR_USER_AGENT / DART_API_KEY from .env
    ap = argparse.ArgumentParser(description="One-page research pack (US/EDGAR, KR/DART).")
    ap.add_argument("query", help="ticker or company name, e.g. NVDA, 'nvidia', or 삼성전자")
    ap.add_argument("--no-price", action="store_true", help="skip the demo price snapshot (no yfinance call)")
    ap.add_argument("--save", action="store_true", help="write data/output/<TICKER>.research.md")
    args = ap.parse_args(argv)

    us = build_us_pack(args.query, with_price=not args.no_price)
    if us is not None:
        md = render_markdown(us)
        ticker = us.profile.tickers[0] if us.profile.tickers else args.query.upper()
    else:
        # Korean path (Open DART). Needs DART_API_KEY; latest completed FY.
        try:
            from engine.research_pack_kr import build_kr_pack, render_markdown_kr

            kr = build_kr_pack(args.query, year=date.today().year - 1)
        except RuntimeError as exc:   # DART_API_KEY not set
            print(f"'{args.query}' is not a US (EDGAR) issuer, and the KR (DART) path needs a key.\n  {exc}",
                  file=sys.stderr)
            return 2
        if kr is None:
            print(f"'{args.query}' did not resolve in SEC EDGAR (US) or Open DART (KR).", file=sys.stderr)
            return 2
        md = render_markdown_kr(kr)
        ticker = kr.profile.stock_code or args.query.upper()

    print(md)

    if args.save:
        out = ROOT / "data" / "output" / f"{ticker}.research.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md + "\n", encoding="utf-8")
        print(f"\n[saved] {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
