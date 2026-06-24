"""Run the serverless search handler locally for testing (no deploy needed).

    python scripts/serve_api.py 8800
    curl 'http://localhost:8800/api/research?ticker=TSLA'

Loads api/research.py's Vercel `handler` class and serves it on a local HTTP server, so
the exact production code path is exercised before deploying. Reads EDGAR_USER_AGENT / keys
from .env.
"""

from __future__ import annotations

import importlib.util
import sys
from http.server import HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(str(ROOT / ".env"))

# Load api/research.py by path (api/ isn't a package; Vercel treats each file standalone).
_spec = importlib.util.spec_from_file_location("research_api", ROOT / "api" / "research.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8800
    print(f"serving api/research handler on http://127.0.0.1:{port}  (try /api/research?ticker=TSLA)")
    HTTPServer(("127.0.0.1", port), _mod.handler).serve_forever()
