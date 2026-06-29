"""Canonical full build of docs/pack.html — fetches everything FRESH and bakes it in.

One script (used manually and by the daily refresh in scripts/refresh_and_deploy.sh) that
reproduces the complete live page so we never drift back to ad-hoc re-injection:

  - Featured US (EDGAR): full pack + peer comparison + analyst consensus
  - Featured KR (DART): full Korean pack
  - Market psychology (Treasury / CFTC / FRED) baked once, incl. Korea macro

Needs .env keys (DART_API_KEY, FRED_API_KEY, FINNHUB_API_KEY, EDGAR_USER_AGENT).
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
from datetime import date

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from engine import peers as peers_mod  # noqa: E402
from engine.analysts import analyst_consensus  # noqa: E402
from engine.market import build_market_context  # noqa: E402
from engine.research_pack import build_us_pack, to_page_dict  # noqa: E402
from engine.research_pack_kr import build_kr_pack, to_kr_page_dict  # noqa: E402

# TEMPLATE lives in build_pack_page.py (single source of the HTML shell)
_spec = importlib.util.spec_from_file_location("bpp", ROOT / "scripts" / "build_pack_page.py")
_bpp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_bpp)
TEMPLATE = _bpp.TEMPLATE

FEATURED_US = ["NVDA", "AAPL", "AMD", "MU"]
FEATURED_KR = ["005930", "000660", "005380", "035720"]


def main() -> int:
    packs: list[dict] = []

    for t in FEATURED_US:
        try:
            pack = build_us_pack(t)
            if pack is None:
                print(f"  skip US {t} (no EDGAR resolve)", file=sys.stderr)
                continue
            d = to_page_dict(pack)
            pr = peers_mod.peers_for(t)
            if pr:
                d["peers"] = pr
            a = analyst_consensus(t)
            if a:
                d["analysts"] = a
            packs.append(d)
            print(f"  US {t}: peers={'y' if pr else 'n'} analysts={'y' if a else 'n'}", file=sys.stderr)
        except Exception as exc:
            print(f"  ERROR US {t}: {exc}", file=sys.stderr)

    yr = date.today().year - 1
    for t in FEATURED_KR:
        try:
            kr = build_kr_pack(t, year=yr)
            if kr:
                packs.append(to_kr_page_dict(kr))
                print(f"  KR {t}: {kr.profile.corp_name}", file=sys.stderr)
            else:
                print(f"  skip KR {t} (no DART resolve)", file=sys.stderr)
        except Exception as exc:
            print(f"  ERROR KR {t}: {exc}", file=sys.stderr)

    if not packs:
        print("no packs built — aborting (leaving docs/pack.html untouched)", file=sys.stderr)
        return 1

    market = build_market_context()
    payload = json.dumps(packs, ensure_ascii=False).replace("<", "\\u003c")
    mkt = json.dumps(market, ensure_ascii=False).replace("<", "\\u003c")
    html = TEMPLATE.replace("__DATA__", payload).replace("__MARKET__", mkt)
    from engine.webnav import nav
    html = html.replace("<body>", "<body>" + nav("home"))   # shared top nav (incl. ⚙️ 설정)
    assert "__DATA__" not in html and "__MARKET__" not in html, "unfilled placeholder"

    out = ROOT / "docs" / "pack.html"
    out.write_text(html, encoding="utf-8")
    print(
        f"wrote {out} — {len(packs)} packs, {len(html):,} bytes | "
        f"positioning {len(market.get('positioning', []))} | "
        f"macro {len(market.get('macro') or {})} | kr_macro {len(market.get('kr_macro') or {})}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
