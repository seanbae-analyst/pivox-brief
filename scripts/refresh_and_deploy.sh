#!/usr/bin/env bash
# Daily fresh rebuild + deploy of pivox-brief.
# Run by launchd (com.pivoxbrief.refresh) and manually. Self-bootstraps PATH because launchd
# runs with a minimal environment. Refreshes GitHub Pages (git push) and Vercel (CLI auth).
set -uo pipefail

export HOME="${HOME:-/Users/seanbae}"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
[ -s "$HOME/.nvm/nvm.sh" ] && . "$HOME/.nvm/nvm.sh" >/dev/null 2>&1   # puts node + vercel on PATH

REPO="$HOME/Desktop/취준/pivox-brief"
cd "$REPO" || { echo "no repo at $REPO"; exit 1; }
echo "===== refresh $(date '+%F %T') ====="

# 1. fresh build (build_site.py aborts itself on total failure, leaving the page untouched)
./venv/bin/python scripts/build_site.py || { echo "build failed — abort"; exit 1; }

# 2. JS sanity gate — never ship a page whose script won't parse
./venv/bin/python - <<'PY'
import re, pathlib
h = pathlib.Path("docs/pack.html").read_text(encoding="utf-8")
pathlib.Path("/tmp/pb_refresh_check.js").write_text(re.search(r"<script>(.*)</script>", h, re.S).group(1))
PY
if command -v node >/dev/null 2>&1; then
  node --check /tmp/pb_refresh_check.js || { echo "JS check failed — abort, restoring last-good"; git checkout -- docs/pack.html 2>/dev/null; exit 1; }
fi

# 3. Morning market-psychology brief — email + web page, on the same fresh data. Done BEFORE
#    the commit/deploy so docs/brief.html ships in this run. Delivery is key-gated (inert
#    without GMAIL_APP_PASSWORD/SENDGRID). Never blocks the refresh.
./venv/bin/python scripts/brief.py --send --web --quiet || echo "brief step failed (non-fatal)"

# 4. commit + push -> GitHub Pages auto-refreshes (pack + brief)
if [ -n "$(git status --porcelain docs/pack.html docs/brief.html)" ]; then
  git add docs/pack.html docs/brief.html
  git commit -q -m "chore(refresh): daily data + brief ($(date +%F))"
  git push -q && git push -q origin feat/refined-signals:main && echo "pushed -> Pages"
else
  echo "no data change"
fi

# 5. Vercel redeploy (local CLI auth — no token needed)
if command -v vercel >/dev/null 2>&1; then
  vercel --prod --yes --scope seanbae-analysts-projects >/dev/null 2>&1 \
    && echo "deployed -> Vercel" || echo "vercel deploy FAILED (CLI auth may have expired — run: vercel login)"
fi

echo "===== done $(date '+%T') ====="
