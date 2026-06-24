# Deploy — the hybrid research pack

The page is a **hybrid**: featured tickers are baked into a static page (full pack incl.
price multiples + the AI Signal read); a **search box** fetches any other US issuer live
from a tiny serverless function.

```
docs/pack.html        static frontend (GitHub Pages + Vercel)
api/research.py        serverless search endpoint  →  /api/research?ticker=TSLA
```

Why a backend at all: SEC EDGAR does **not** send CORS headers, so a static page cannot
fetch it from the browser. The function fetches EDGAR server-side and returns the same
shape the page renders. Searched tickers show financials / margins / health / filings /
insider / coverage — **not** price multiples (yfinance is blocked from cloud IPs) or the
Signal read (that is the $0 Claude-in-session layer, cached for featured tickers only).

## Local dev (no deploy)

```bash
# 1. run the search API locally
./venv/bin/python scripts/serve_api.py 8800

# 2. serve the page and open it (localhost auto-points the search box at :8800)
./venv/bin/python -m http.server 8799 --directory docs
#   → open http://localhost:8799/pack.html  and search e.g. TSLA
```

## Deploy to Vercel (free hobby tier, ~2 min)

1. Create a free account at vercel.com and install the CLI: `npm i -g vercel`
2. From the repo root: `vercel link` (link to a new/existing project).
3. Set the SEC fair-access identity (required) in the Vercel project env:
   `vercel env add EDGAR_USER_AGENT` → enter `your name your@email.com`
4. Ship it: `vercel --prod`

Result: `https://<project>.vercel.app/pack.html` — featured tickers **and** working search
(same origin, so the page calls `/api/research` with no extra config).

## Keeping the GitHub Pages URL

GitHub Pages keeps serving the static page at `seanbae-analyst.github.io/pivox-brief/pack.html`
(featured tickers only — no backend there). To make **search work on the Pages URL too**, point
it at the deployed API by adding one line before `</head>` in `docs/pack.html` (or via the
generator): `<script>window.PIVOX_API_BASE='https://<project>.vercel.app'</script>`. The function
already sends `Access-Control-Allow-Origin: *`, so the cross-origin call is allowed.

## Notes

- `api/requirements.txt` is intentionally lean (requests + pydantic) for fast cold starts.
- Regenerate the static page after adding featured tickers / refreshing data:
  `python scripts/build_pack_page.py NVDA AAPL AMD 삼성전자 SK하이닉스`
- Not investment advice — descriptive analysis from official filings only (DATA_SOURCES.md).
