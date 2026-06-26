#!/usr/bin/env python3
"""Local picker server — click-to-choose your brief settings without any cloud.

  python scripts/serve_settings.py        # then open http://localhost:8800/settings.html

Serves docs/ and handles GET /load + POST /save against the local data/watchlist.json that the
morning brief reads. This is the self-contained version of the public Supabase picker — same
page, same selection, no account needed. (The public homepage version uses Supabase; this one
writes the local file directly.)
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DOCS = ROOT / "docs"

from engine.watchlist import load, save  # noqa: E402

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8800


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body=b"", ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def log_message(self, *a):  # quiet
        pass

    def do_GET(self):
        if self.path.startswith("/load"):
            self._send(200, json.dumps(load(), ensure_ascii=False).encode("utf-8"))
            return
        rel = self.path.lstrip("/") or "settings.html"
        f = (DOCS / rel).resolve()
        if not str(f).startswith(str(DOCS)) or not f.is_file():
            self._send(404, b'{"error":"not found"}')
            return
        ctype = "text/html; charset=utf-8" if f.suffix == ".html" else "application/octet-stream"
        self._send(200, f.read_bytes(), ctype)

    def do_POST(self):
        if not self.path.startswith("/save"):
            self._send(404, b'{"error":"not found"}')
            return
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8"))
            save({"themes": body.get("themes", []), "custom": body.get("custom", []),
                  "explain_level": body.get("explain_level", "초보")})
            self._send(200, json.dumps(load(), ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self._send(400, json.dumps({"error": str(e)}).encode("utf-8"))


if __name__ == "__main__":
    print(f"픽커 열기 → http://localhost:{PORT}/settings.html   (Ctrl+C 로 종료)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
