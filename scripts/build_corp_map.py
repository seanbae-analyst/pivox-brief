"""Build the bundled listed-only DART corpCode map → data/dart_corp_listed.json.

The serverless KR search path resolves a ticker/name to a DART corp_code. Downloading the
full corpCode.xml ZIP (~100k entries) on every cold start blows the function time limit, so
we bundle a slim listed-only map (stock_code present) into the deployment. Refresh with:

    python scripts/build_corp_map.py        # needs DART_API_KEY in .env
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

from engine import dart  # noqa: E402

load_dotenv()


def main() -> int:
    corps = dart.parse_corp_codes(dart._get_bytes("corpCode.xml"))
    listed = [{"c": c.corp_code, "n": c.corp_name, "s": c.stock_code} for c in corps if c.stock_code]
    out = Path(__file__).resolve().parent.parent / "data" / "dart_corp_listed.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(listed, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out} — {len(listed)} listed corps ({out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
