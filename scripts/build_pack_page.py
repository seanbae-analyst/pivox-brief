"""Build a self-contained stock-pack web page (RESEARCH_PACK_PLAN.md step 6).

    EDGAR_USER_AGENT="you you@example.com" python scripts/build_pack_page.py NVDA AAPL AMD

Fetches each ticker's research pack from SEC EDGAR, inlines the data into a single
docs/pack.html with a ticker selector. Static + self-contained — works opened
locally and on GitHub Pages (no fetch/CORS), matching the project's $0 dashboard.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import edgar  # noqa: E402
from engine.research_pack import build_us_pack, earnings_read  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"


def _d(obj):
    return asdict(obj) if is_dataclass(obj) else obj


def pack_to_dict(pack) -> dict:
    er = earnings_read(pack.filings)
    return {
        "ticker": pack.profile.tickers[0] if pack.profile.tickers else pack.query.upper(),
        "name": pack.profile.name,
        "exchanges": pack.profile.exchanges,
        "industry": pack.profile.sic_description,
        "cik": pack.profile.cik,
        "language": pack.language,
        "price": _d(pack.price),
        "trend": [_d(r) for r in pack.trend],
        "earnings_read": {k: _d(v) for k, v in er.items()},
        "filings": [{**_d(f), "labels": edgar.decode_items(f.items)} for f in pack.filings],
        "news": [_d(n) for n in pack.news],
        "sources": pack.sources,
    }


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage: build_pack_page.py <TICKER> [TICKER ...]", file=sys.stderr)
        return 2

    packs = []
    for query in args:
        pack = build_us_pack(query)
        if pack is None:
            print(f"  skip: '{query}' did not resolve in EDGAR", file=sys.stderr)
            continue
        packs.append(pack_to_dict(pack))
        print(f"  built {packs[-1]['ticker']}", file=sys.stderr)

    if not packs:
        print("no packs built", file=sys.stderr)
        return 1

    DOCS.mkdir(parents=True, exist_ok=True)
    # Escape '<' so a stray '</script>' in inlined data can't break the page.
    payload = json.dumps(packs, ensure_ascii=False).replace("<", "\\u003c")
    html = TEMPLATE.replace("__DATA__", payload)
    out = DOCS / "pack.html"
    out.write_text(html, encoding="utf-8")
    print(f"Built {out}  ({len(html):,} bytes, {len(packs)} stock(s))")
    return 0


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pivox Brief — Research Pack</title>
<style>
:root{--ink:#0f172a;--muted:#64748b;--line:#e6e8ec;--soft:#f8fafc;--accent:#0d9488;--up:#0d9488;--down:#dc2626}
*{box-sizing:border-box}
body{margin:0;background:#fff;color:var(--ink);font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:920px;margin:0 auto;padding:28px 20px 64px}
h1{font-size:20px;margin:0 0 2px;letter-spacing:-.01em}
.sub{color:var(--muted);font-size:13px;margin:0 0 18px}
.sel{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:22px}
.sel button{appearance:none;border:1px solid var(--line);background:#fff;border-radius:8px;padding:7px 12px;font:600 13px sans-serif;color:var(--muted);cursor:pointer}
.sel button.on{border-color:var(--accent);color:var(--ink);background:var(--soft)}
h2.name{font-size:22px;margin:0 0 2px;letter-spacing:-.01em}
.meta{color:var(--muted);font-size:12px;margin:0 0 18px}
.chips{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:20px}
.chip{border:1px solid var(--line);border-radius:10px;padding:8px 12px;min-width:92px}
.chip b{display:block;font-size:17px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.chip span{color:var(--muted);font-size:11px}
.card{border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:16px}
.card h3{margin:0 0 12px;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.03em}
td.num,th.num{text-align:right;font-family:ui-monospace,Menlo,monospace}
.up{color:var(--up)}.down{color:var(--down)}
a{color:#0e7490;text-decoration:none}a:hover{text-decoration:underline}
ul.list{margin:0;padding:0;list-style:none}
ul.list li{padding:7px 0;border-bottom:1px solid var(--line);font-size:13px}
ul.list li:last-child{border:0}
.tag{display:inline-block;background:var(--soft);border:1px solid var(--line);border-radius:6px;padding:1px 7px;font-size:11px;margin-left:4px;color:#475569}
.lead{border-left:3px solid var(--accent);padding-left:12px;margin:8px 0}
.foot{color:var(--muted);font-size:12px;margin-top:24px;border-top:1px solid var(--line);padding-top:14px}
</style>
</head>
<body>
<div class="wrap">
<h1>Pivox Brief — Research Pack</h1>
<p class="sub">One page of price-relevant factors from official SEC filings. A research starting point — not investment advice.</p>
<div class="sel" id="sel"></div>
<div id="pack"></div>
<div class="foot">Financials &amp; filings: SEC EDGAR (XBRL), keyless. Prices: demo / illustrative only. News: headlines + links only. Built for $0. Descriptive analysis, not investment advice.</div>
</div>
<script>
const DATA = __DATA__;
const $=(t,c,h)=>{const e=document.createElement(t);if(c)e.className=c;if(h!=null)e.innerHTML=h;return e;};
const usd=v=>{if(v==null)return '\\u2014';const a=Math.abs(v);if(a>=1e9)return '$'+(v/1e9).toFixed(2)+'B';if(a>=1e6)return '$'+(v/1e6).toFixed(0)+'M';return '$'+v.toLocaleString();};
const pct=(v,s)=>v==null?'\\u2014':(s&&v>=0?'+':'')+v.toFixed(1)+'%';
const esc=s=>(s==null?'':String(s)).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));

function fileRow(f){
  if(!f)return '';
  const lbl=(f.labels&&f.labels.length)?' \\u2014 '+esc(f.labels.join('; ')):'';
  return '<a href="'+esc(f.url)+'" target="_blank" rel="noopener">'+esc(f.primary_document||'filing')+'</a> \\u00b7 filed '+esc(f.filing_date)+lbl;
}

function render(p){
  const box=document.getElementById('pack');box.innerHTML='';
  box.append($('h2','name',esc(p.name)+' <span style="color:var(--muted);font-weight:600">('+esc(p.ticker)+')</span>'));
  box.append($('p','meta',[p.exchanges.join(', '),esc(p.industry),'CIK '+esc(p.cik)].filter(Boolean).join(' \\u00b7 ')));

  const t=p.trend||[];const last=t[t.length-1];
  const chips=$('div','chips');
  if(p.price){const c=$('div','chip');c.append($('b',null,'$'+p.price.close),$('span',null,'last close '+p.price.date+' (demo)'));chips.append(c);}
  if(last){
    [['Revenue',usd(last.revenue)],['Rev YoY',pct(last.revenue_yoy_pct,true)],['Gross margin',pct(last.gross_margin)],['Diluted EPS',last.eps_diluted!=null?'$'+last.eps_diluted.toFixed(2):'\\u2014']].forEach(([s,v])=>{const c=$('div','chip');c.append($('b',null,v),$('span',null,s+' \\u00b7 '+esc(last.period)));chips.append(c);});
  }
  box.append(chips);

  if(t.length){
    const card=$('div','card');card.append($('h3',null,'Financial trend (quarterly, SEC XBRL)'));
    let h='<table><tr><th>Period</th><th class="num">Revenue</th><th class="num">Rev YoY</th><th class="num">Gross %</th><th class="num">Oper %</th><th class="num">Net %</th><th class="num">Diluted EPS</th></tr>';
    t.forEach(r=>{const y=r.revenue_yoy_pct;h+='<tr><td>'+esc(r.period)+'</td><td class="num">'+usd(r.revenue)+'</td><td class="num '+(y==null?'':y>=0?'up':'down')+'">'+pct(y,true)+'</td><td class="num">'+pct(r.gross_margin)+'</td><td class="num">'+pct(r.operating_margin)+'</td><td class="num">'+pct(r.net_margin)+'</td><td class="num">'+(r.eps_diluted!=null?'$'+r.eps_diluted.toFixed(2):'\\u2014')+'</td></tr>';});
    h+='</table>';card.innerHTML+=h;box.append(card);
  }

  const er=p.earnings_read||{};
  if(er.earnings_8k||er.latest_10q||er.latest_10k){
    const card=$('div','card');card.append($('h3',null,'Earnings read'));
    [['Latest earnings release (8-K, Results of operations)',er.earnings_8k],['Latest 10-Q (MD&A + financials)',er.latest_10q],['Risk factors (Item 1A, latest 10-K)',er.latest_10k]].forEach(([lbl,f])=>{if(f){const d=$('div','lead');d.innerHTML='<b>'+lbl+'</b><br>'+fileRow(f);card.append(d);}});
    box.append(card);
  }

  if((p.filings||[]).length){
    const card=$('div','card');card.append($('h3',null,'Recent filings'));
    const ul=$('ul','list');p.filings.forEach(f=>{const li=$('li');li.innerHTML='<b>'+esc(f.form)+'</b> '+fileRow(f);ul.append(li);});card.append(ul);box.append(card);
  }

  const nc=$('div','card');nc.append($('h3',null,'News & catalysts \\u2014 headlines + links only'));
  if((p.news||[]).length){const ul=$('ul','list');p.news.forEach(n=>{const meta=[n.source,n.date].filter(Boolean).join(' \\u00b7 ');const li=$('li');li.innerHTML='<a href="'+esc(n.url)+'" target="_blank" rel="noopener">'+esc(n.headline)+'</a>'+(meta?' <span class="tag">'+esc(meta)+'</span>':'');ul.append(li);});nc.append(ul);}
  else nc.append($('p',null,'<span style="color:var(--muted)">No cached headlines for this ticker.</span>'));
  box.append(nc);

  if((p.sources||[]).length){const card=$('div','card');card.append($('h3',null,'Sources'));const ul=$('ul','list');p.sources.forEach(s=>{const li=$('li');const m=String(s).match(/(https?:\\/\\/\\S+)/);li.innerHTML=m?esc(s.replace(m[1],''))+'<a href="'+esc(m[1])+'" target="_blank" rel="noopener">'+esc(m[1])+'</a>':esc(s);ul.append(li);});card.append(ul);box.append(card);}
}

function build(){
  const sel=document.getElementById('sel');
  DATA.forEach((p,i)=>{const b=$('button',i===0?'on':null,esc(p.ticker));b.onclick=()=>{document.querySelectorAll('.sel button').forEach(x=>x.classList.remove('on'));b.classList.add('on');render(p);};sel.append(b);});
  if(DATA.length)render(DATA[0]);
}
build();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
