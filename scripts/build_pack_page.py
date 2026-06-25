"""Build a self-contained stock-pack web page (RESEARCH_PACK_PLAN.md step 6).

    python scripts/build_pack_page.py NVDA AAPL AMD 삼성전자 SK하이닉스

Fetches each query's research pack — US via SEC EDGAR, KR via Open DART — and inlines
the data into a single docs/pack.html with a ticker selector. Each pack renders in its
own language (US → English, KR → Korean). Static + self-contained (no fetch/CORS),
matching the project's $0 dashboard. Reads EDGAR_USER_AGENT / DART_API_KEY from .env.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, is_dataclass
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402
from engine import edgar  # noqa: E402
from engine.research_pack import build_us_pack, to_page_dict  # noqa: E402
from engine.market import build_market_context  # noqa: E402

load_dotenv()  # EDGAR_USER_AGENT / DART_API_KEY from .env

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"


def _d(obj):
    return asdict(obj) if is_dataclass(obj) else obj


def kr_pack_to_dict(pack) -> dict:
    p = pack.profile
    return {
        "language": "ko",
        "ticker": p.stock_code or pack.query,
        "name": p.corp_name,
        "name_eng": p.corp_name_eng,
        "exchanges": ["KRX"],
        "cik": p.corp_code,                      # DART 고유번호 (rendered as "DART …")
        "price": None,
        # normalize label -> period so the page renderer reads trends uniformly (US uses `period`)
        "trend": [{"period": r.label, "revenue": r.revenue, "gross_margin": r.gross_margin,
                   "operating_margin": r.operating_margin, "net_margin": r.net_margin,
                   "revenue_yoy_pct": r.revenue_yoy_pct} for r in pack.trend],
        "disclosures": [_d(d) for d in pack.disclosures],
        "news": [_d(n) for n in pack.news],
        "sources": pack.sources,
    }


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage: build_pack_page.py <TICKER|name> [...]", file=sys.stderr)
        return 2

    from engine.research_pack_kr import build_kr_pack

    packs = []
    for query in args:
        us = build_us_pack(query)
        if us is not None:
            packs.append(to_page_dict(us))
        else:
            try:
                kr = build_kr_pack(query, year=date.today().year - 1)
            except RuntimeError as exc:   # DART_API_KEY missing
                print(f"  skip: '{query}' not in EDGAR and KR needs a key ({exc})", file=sys.stderr)
                continue
            if kr is None:
                print(f"  skip: '{query}' did not resolve in EDGAR or DART", file=sys.stderr)
                continue
            packs.append(kr_pack_to_dict(kr))
        print(f"  built {packs[-1]['ticker']} ({packs[-1]['language']})", file=sys.stderr)

    if not packs:
        print("no packs built", file=sys.stderr)
        return 1

    DOCS.mkdir(parents=True, exist_ok=True)
    # Escape '<' so a stray '</script>' in inlined data can't break the page.
    payload = json.dumps(packs, ensure_ascii=False).replace("<", "\\u003c")
    market = json.dumps(build_market_context(), ensure_ascii=False).replace("<", "\\u003c")
    html = TEMPLATE.replace("__DATA__", payload).replace("__MARKET__", market)
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
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Inter:wght@400;500;600;700&family=Playfair+Display:wght@600;700&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#0a0b0d;--panel:#101317;--panel2:#161a20;--soft:#161a20;
  --ink:#ECEAE3;--muted:#8b919b;--faint:#5f656e;
  --line:rgba(255,255,255,.08);--line2:rgba(255,255,255,.05);
  --accent:#c6a063;--accent2:#dcb979;--accent-dim:rgba(198,160,99,.13);
  --up:#5ec08a;--down:#e26d60;--amber:#d6a44f;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
  --serif:"Playfair Display",Georgia,"Times New Roman",serif;
  --sans:"Inter",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 var(--sans);-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
::selection{background:var(--accent-dim)}
.wrap{max-width:960px;margin:0 auto;padding:48px 24px 80px}
h1{font:600 30px/1.15 var(--serif);margin:0 0 6px;letter-spacing:.01em}
.sub{color:var(--muted);font-size:13.5px;margin:0 0 26px;max-width:680px}
.search{display:flex;gap:10px;margin:0 0 10px}
.search input{flex:1;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:11px 14px;font:14px var(--sans);color:var(--ink)}
.search input::placeholder{color:var(--faint)}
.search input:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-dim)}
.search button{border:1px solid var(--accent);background:var(--accent);color:#0a0b0d;border-radius:10px;padding:11px 20px;font:600 13px var(--sans);cursor:pointer;transition:filter .15s}
.search button:hover{filter:brightness(1.08)}
.searchmsg{color:var(--muted);font-size:12px;min-height:16px;margin:0 0 8px}
.searchnote{background:var(--accent-dim);border:1px solid var(--line);border-left:2px solid var(--accent);border-radius:10px;padding:10px 14px;margin:0 0 18px;font-size:12.5px;color:var(--ink)}
.sel{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 30px}
.sel button{appearance:none;border:1px solid var(--line);background:var(--panel);border-radius:999px;padding:8px 16px;font:600 12.5px var(--mono);letter-spacing:.02em;color:var(--muted);cursor:pointer;transition:all .15s}
.sel button:hover{color:var(--ink)}
.sel button.on{border-color:var(--accent);color:var(--accent2);background:var(--accent-dim)}
h2.name{font:700 30px/1.1 var(--serif);margin:0 0 4px;letter-spacing:.01em}
h2.name span{color:var(--accent)!important;font-family:var(--mono)!important;font-size:.58em;letter-spacing:.04em}
.meta{color:var(--muted);font:12px/1.5 var(--mono);margin:0 0 22px;letter-spacing:.02em}
.chips{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:22px}
.chip{position:relative;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 16px 12px 18px;min-width:108px;overflow:hidden}
.chip::before{content:"";position:absolute;left:0;top:0;bottom:0;width:2px;background:var(--accent);opacity:.55}
.chip b{display:block;font:600 19px var(--mono);color:var(--ink);letter-spacing:-.01em}
.chip span{display:block;margin-top:4px;color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.06em}
.card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:20px 22px;margin-bottom:16px}
.card h3{display:flex;align-items:center;gap:9px;margin:0 0 16px;font:600 11px var(--sans);text-transform:uppercase;letter-spacing:.14em;color:var(--accent2)}
.card h3::before{content:"";width:16px;height:1.5px;background:var(--accent);opacity:.7}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line2)}
tr:last-child td{border-bottom:0}
th{color:var(--muted);font-weight:600;font-size:10.5px;text-transform:uppercase;letter-spacing:.07em}
tbody tr:hover td{background:var(--panel2)}
td{color:var(--ink)}
td.num,th.num{text-align:right;font-family:var(--mono)}
.up{color:var(--up)}.down{color:var(--down)}
a{color:var(--accent2);text-decoration:none;border-bottom:1px solid transparent;transition:border-color .15s}
a:hover{border-bottom-color:var(--accent2)}
ul.list{margin:0;padding:0;list-style:none}
ul.list li{padding:11px 0;border-bottom:1px solid var(--line2);font-size:13.5px;line-height:1.65}
ul.list li:last-child{border:0}
ul.list b{color:var(--ink);font-weight:600}
.tag{display:inline-block;background:var(--accent-dim);border:1px solid var(--line);border-radius:6px;padding:1px 8px;font:500 10.5px var(--mono);letter-spacing:.02em;margin:0 4px;color:var(--accent2);text-transform:uppercase;vertical-align:middle}
.lead{border-left:2px solid var(--accent);padding-left:14px;margin:10px 0;color:var(--muted)}
.foot{color:var(--faint);font-size:11.5px;margin-top:30px;border-top:1px solid var(--line);padding-top:16px;line-height:1.7}
.statgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}
.stat{background:var(--panel2);border:1px solid var(--line2);border-radius:10px;padding:11px 13px}
.stat b{display:block;font:600 16px var(--mono);color:var(--ink)}
.stat span{display:block;margin-top:4px;color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.05em}
.priceline{margin-top:14px;padding-top:13px;border-top:1px solid var(--line2);font:12px/1.9 var(--mono);color:var(--muted)}
.conf{color:var(--faint);font:11px var(--mono)}
.subh{font-weight:700;font-size:12px;color:var(--ink);margin:14px 0 4px;letter-spacing:.02em}
.fineprint{color:var(--faint);font-size:11px;margin-top:12px}
.covrow{padding:9px 0;font-size:12.5px;border-bottom:1px solid var(--line2);line-height:1.7;color:var(--muted)}
.covrow:last-child{border:0}
.covlabel{font-weight:700;margin-right:6px;white-space:nowrap}
.cov-ok{color:var(--up)}.cov-mid{color:var(--amber)}.cov-out{color:var(--down)}
[hidden]{display:none!important}
.hero{padding:8px 0}
#home{position:relative;min-height:66vh;display:flex;flex-direction:column;justify-content:center}
#home::before{content:"";position:absolute;left:50%;top:34%;transform:translate(-50%,-50%);width:680px;max-width:88vw;height:360px;background:radial-gradient(ellipse at center,rgba(198,160,99,.10),transparent 70%);pointer-events:none;z-index:0}
.hero{position:relative;z-index:1;animation:heroIn .5s ease both}
@keyframes heroIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
@media(prefers-reduced-motion:reduce){.hero{animation:none}}
.examples{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:18px}
.examples .lbl{color:var(--faint);font:600 10px var(--mono);text-transform:uppercase;letter-spacing:.14em;margin-right:2px}
.ex{appearance:none;border:1px solid var(--line);background:transparent;color:var(--muted);border-radius:999px;padding:5px 13px;font:600 12px var(--mono);cursor:pointer;transition:border-color .15s,color .15s,background .15s}
.ex:hover{border-color:var(--accent);color:var(--accent2);background:var(--accent-dim)}
.kicker{font:600 11px var(--mono);letter-spacing:.18em;text-transform:uppercase;color:var(--accent);margin:0 0 14px}
.hero h1{font-size:46px;margin:0 0 14px}
.hero .sub{margin-bottom:22px}
.hero .search{max-width:560px}
.ftitle{display:flex;align-items:center;gap:9px;font:600 11px var(--sans);text-transform:uppercase;letter-spacing:.14em;color:var(--muted);margin:0 0 16px}
.ftitle::before{content:"";width:16px;height:1.5px;background:var(--accent);opacity:.7}
.featured{display:grid;grid-template-columns:repeat(auto-fill,minmax(238px,1fr));gap:12px}
.fcard{appearance:none;display:block;width:100%;text-align:left;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px;cursor:pointer;color:var(--ink);font-family:var(--sans);transition:border-color .15s,transform .15s,background .15s}
.fcard:hover{border-color:var(--accent);background:var(--panel2);transform:translateY(-2px)}
.fc-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:11px}
.fc-tkr{font:600 18px var(--mono);color:var(--accent2);letter-spacing:.02em}
.fc-badge{font:600 9px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--accent);border:1px solid var(--line);background:var(--accent-dim);border-radius:5px;padding:2px 7px}
.fc-name{font:600 15px var(--serif);color:var(--ink);margin:0 0 3px}
.fc-meta{font:11px var(--mono);color:var(--muted);margin:0 0 14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.fc-stats{display:flex;gap:16px;font:600 13px var(--mono);color:var(--ink);border-top:1px solid var(--line2);padding-top:12px}
.fc-stats .up{color:var(--up)}.fc-stats .down{color:var(--down)}
.back{display:inline-flex;align-items:center;gap:6px;font:600 12px var(--mono);letter-spacing:.02em;color:var(--muted);text-decoration:none;border:0;cursor:pointer;margin:0 0 22px}
.back:hover{color:var(--accent2)}
@media(max-width:560px){.wrap{padding:32px 16px 64px}h1,.hero h1{font-size:27px}h2.name{font-size:25px}.card{padding:16px}.featured{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="wrap">
<section id="home">
<div class="hero">
<div class="kicker">Equity research · official filings only</div>
<h1>Pivox Brief</h1>
<p class="sub">One page of price-relevant factors from official filings — SEC EDGAR (US) &amp; Open DART (KR). A research starting point — not investment advice.</p>
<form class="search" id="search"><input id="q" type="text" placeholder="Search US or KR — e.g. TSLA, MU, 005930, 카카오" autocomplete="off" spellcheck="false"><button type="submit">Search</button></form>
<div class="searchmsg" id="searchmsg"></div>
<div class="examples" id="examples"></div>
</div>
</section>
<section id="result" hidden>
<a class="back" id="back" href="#">&larr; Search</a>
<div id="pack"></div>
</section>
<div class="foot">US: SEC EDGAR (XBRL) · KR: Open DART · prices = demo only · news = headlines + links only · built for $0. Descriptive analysis, not investment advice / 투자자문이 아닙니다.</div>
</div>
<script>
const DATA = __DATA__;
const MARKET = __MARKET__;
const $=(t,c,h)=>{const e=document.createElement(t);if(c)e.className=c;if(h!=null)e.innerHTML=h;return e;};
const usd=v=>{if(v==null)return '\\u2014';const a=Math.abs(v);if(a>=1e9)return '$'+(v/1e9).toFixed(2)+'B';if(a>=1e6)return '$'+(v/1e6).toFixed(0)+'M';return '$'+v.toLocaleString();};
const pct=(v,s)=>v==null?'\\u2014':(s&&v>=0?'+':'')+v.toFixed(1)+'%';
const won=v=>{if(v==null)return '\\u2014';const a=Math.abs(v);if(a>=1e12)return (v/1e12).toFixed(1)+'조원';if(a>=1e8)return Math.round(v/1e8)+'억원';return v.toLocaleString()+'원';};
const esc=s=>(s==null?'':String(s)).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const conf=c=>c==null?'':' <span class="conf">conf '+c+'</span>';
const mult=v=>v==null?'\\u2014':v+'\\u00d7';
const nmRoe=v=>v==null?'\\u2014':(Math.abs(v)>100?'n/m':pct(v));

function valuationCard(p){
  const q=p.quant; if(!q) return null;
  const v=q.valuation||{},pr=q.profitability||{},h=q.health||{},c=q.capital_return||{},px=q.price||{};
  const card=$('div','card');card.append($('h3',null,'Valuation & quality'));
  const grid=$('div','statgrid');
  const stat=(label,val)=>{const s=$('div','stat');s.append($('b',null,val),$('span',null,label));return s;};
  const num=x=>x==null?'\\u2014':x;
  [['Market cap',usd(v.market_cap)],['P/E (TTM)',mult(v.pe_ttm)],['P/S',mult(v.ps_ttm)],['P/B',mult(v.pb)],['EV/EBITDA',mult(v.ev_ebitda)],
   ['FCF yield',pct(v.fcf_yield_pct)],['Div yield',pct(v.dividend_yield_pct)],['Buyback yield',pct(v.buyback_yield_pct)],['ROE',nmRoe(pr.roe_pct)],
   ['Gross margin',pct(pr.gross_margin_ttm_pct)],['Oper margin',pct(pr.operating_margin_ttm_pct)],['Net margin',pct(pr.net_margin_ttm_pct)],['FCF margin',pct(pr.fcf_margin_pct)],
   ['Net debt',usd(h.net_debt)],['Debt/Equity',num(h.debt_to_equity)],['Current ratio',num(h.current_ratio)],['Shares YoY',pct(c.shares_yoy_pct,true)]
  ].forEach(([l,val])=>grid.append(stat(l,val)));
  card.append(grid);
  if(px&&px.last_close!=null){
    const pl=$('div','priceline');
    pl.innerHTML='<b>Price \\u27e8demo\\u27e9</b> $'+px.last_close+' ('+esc(px.as_of)+') \\u00b7 1M '+pct(px.ret_1m_pct,true)+' \\u00b7 YTD '+pct(px.ret_ytd_pct,true)+' \\u00b7 1Y '+pct(px.ret_1y_pct,true)+' \\u00b7 52w $'+px.low_52w+'\\u2013$'+px.high_52w+' ('+pct(px.pct_from_52w_high,true)+' from high) \\u00b7 MA50 $'+px.ma50+' / MA200 $'+px.ma200;
    card.append(pl);
  }
  return card;
}

function qualitativeCard(p){
  const q=p.qualitative; if(!q||!((q.themes||[]).length||q.guidance||(q.risk_factors||[]).length)) return null;
  const card=$('div','card');card.append($('h3',null,'Signal read \\u2014 qualitative (filings-derived)'));
  if(q.guidance){const d=$('div','lead');d.innerHTML='<b>Guidance:</b> '+esc(q.guidance.direction)+(q.guidance.detail?' \\u2014 '+esc(q.guidance.detail):'')+conf(q.guidance.confidence);card.append(d);}
  if(q.tone){const d=$('div');d.style.margin='8px 0';d.innerHTML='<b>Management tone:</b> '+esc(q.tone.label)+conf(q.tone.confidence);card.append(d);}
  const ul=$('ul','list');
  (q.themes||[]).forEach(t=>{
    const ar=t.direction==='positive'?'<span class="up">\\u25b2</span>':t.direction==='negative'?'<span class="down">\\u25bc</span>':'\\u2022';
    const src=t.source_url?' <a href="'+esc(t.source_url)+'" target="_blank" rel="noopener">src</a>':'';
    const li=$('li');li.innerHTML=ar+' <b>'+esc(t.theme)+'</b> <span class="tag">'+esc(t.direction)+'</span> '+esc(t.evidence)+conf(t.confidence)+src;ul.append(li);
  });
  card.append(ul);
  if((q.risk_factors||[]).length){
    card.append($('div','subh','Key risk factors (10-K Item 1A)'));
    const rl=$('ul','list');q.risk_factors.forEach(r=>{const li=$('li');li.innerHTML=esc(r.summary);rl.append(li);});card.append(rl);
  }
  card.append($('p','fineprint','Themes mapped to a fixed vocabulary; paraphrased from official filings (no verbatim text).'));
  return card;
}

function ownershipCard(p){
  const o=p.ownership; if(!o||!((o.insider_transactions||[]).length||(o.large_holder_filings||[]).length)) return null;
  const card=$('div','card');card.append($('h3',null,'Insider & ownership activity'));
  if(o.insider_pattern&&o.insider_pattern.observation){card.append($('p','fineprint',esc(o.insider_pattern.observation)));}
  const ul=$('ul','list');
  (o.insider_transactions||[]).forEach(t=>{
    const star=t.discretionary?'<span class="up">\\u2605</span> ':'';
    const sh=t.shares!=null?Number(t.shares).toLocaleString():'\\u2014';
    const val=t.value!=null?' (~'+usd(t.value)+')':'';
    const li=$('li');li.innerHTML=star+'<b>'+esc(t.owner)+'</b> <span class="tag">'+esc(t.relationship)+'</span> '+esc(t.code_label)+' '+esc(t.acquired_disposed)+' '+sh+' sh'+val+' \\u00b7 '+esc(t.date||'');ul.append(li);
  });
  card.append(ul);
  if((o.large_holder_filings||[]).length){
    const d=$('div');d.style.marginTop='8px';
    d.innerHTML='<b>Large-holder filings (&gt;5%):</b> '+o.large_holder_filings.slice(0,4).map(f=>'<a href="'+esc(f.url)+'" target="_blank" rel="noopener">'+esc(f.form)+' '+esc(f.filed)+'</a>').join(', ');
    card.append(d);
  }
  card.append($('p','fineprint','\\u2605 = discretionary open-market trade (P/S); others are grants / tax / option / gift.'));
  return card;
}

function coverageCard(p){
  const c=p.coverage; if(!c) return null;
  const card=$('div','card');card.append($('h3',null,'Coverage'));
  const row=(label,items,cls)=>{const d=$('div','covrow');d.innerHTML='<span class="covlabel '+cls+'">'+label+'</span> '+items.map(esc).join(' \\u00b7 ');return d;};
  if((c.covered||[]).length)card.append(row('\\u2705 Covered',c.covered,'cov-ok'));
  if((c.partial||[]).length)card.append(row('\\ud83d\\udfe1 Partial',c.partial,'cov-mid'));
  if((c.structurally_out||[]).length)card.append(row('\\ud83d\\udd34 Out of reach',c.structurally_out,'cov-out'));
  if(c.note)card.append($('p','fineprint',esc(c.note)));
  return card;
}

function qualityCard(p){
  const q=p.quality_flags; if(!q||!q.length) return null;
  const card=$('div','card');card.append($('h3',null,'Quality flags'));
  const ul=$('ul','list');
  q.forEach(f=>{const li=$('li');li.innerHTML=esc(f.observation);ul.append(li);});
  card.append(ul);
  card.append($('p','fineprint','Descriptive observations derived from XBRL \\u2014 not a verdict.'));
  return card;
}

function riskDeltaCard(p){
  const rd=p.risk_delta; if(!rd||!((rd.added||[]).length||(rd.removed||[]).length)) return null;
  const card=$('div','card');card.append($('h3',null,'Risk-factor delta (10-K Item 1A, YoY)'));
  card.append($('p','fineprint','Latest 10-K '+esc(rd.current_filing.filed)+' ('+rd.current_count+' risks) vs prior '+esc(rd.prior_filing.filed)+' ('+rd.prior_count+').'));
  if((rd.added||[]).length){
    card.append($('div','subh','Added this year ('+rd.added.length+')'));
    const ul=$('ul','list');rd.added.forEach(a=>{const li=$('li');li.innerHTML='<span class="up">\\u25b2</span> '+esc(a);ul.append(li);});card.append(ul);
  }
  if((rd.removed||[]).length){
    card.append($('div','subh','Removed this year ('+rd.removed.length+')'));
    const ul=$('ul','list');rd.removed.forEach(r=>{const li=$('li');li.innerHTML='<span class="down">\\u25bd</span> '+esc(r);ul.append(li);});card.append(ul);
  }
  return card;
}

function fileRow(f){
  if(!f)return '';
  const lbl=(f.labels&&f.labels.length)?' \\u2014 '+esc(f.labels.join('; ')):'';
  return '<a href="'+esc(f.url)+'" target="_blank" rel="noopener">'+esc(f.primary_document||'filing')+'</a> \\u00b7 filed '+esc(f.filing_date)+lbl;
}

function peerCard(p){
  const rows=p.peers; if(!rows||!rows.length) return null;
  const t=p.trend||[];const last=t[t.length-1]||{};
  const subj={ticker:p.ticker,revenue:last.revenue,revenue_yoy_pct:last.revenue_yoy_pct,gross_margin:last.gross_margin,net_margin:last.net_margin,roe_pct:((p.quant||{}).profitability||{}).roe_pct};
  const card=$('div','card');card.append($('h3',null,'Peer comparison \\u2014 same-sector (SEC XBRL)'));
  let h='<table><tr><th>Ticker</th><th class="num">Revenue</th><th class="num">Rev YoY</th><th class="num">Gross %</th><th class="num">Net %</th><th class="num">ROE</th></tr>';
  [subj].concat(rows).forEach((r,i)=>{const y=r.revenue_yoy_pct;const hl=i===0?' style="background:var(--accent-dim)"':'';h+='<tr'+hl+'><td><b>'+esc(r.ticker)+'</b></td><td class="num">'+usd(r.revenue)+'</td><td class="num '+(y==null?'':y>=0?'up':'down')+'">'+pct(y,true)+'</td><td class="num">'+pct(r.gross_margin)+'</td><td class="num">'+pct(r.net_margin)+'</td><td class="num">'+nmRoe(r.roe_pct)+'</td></tr>';});
  h+='</table>';card.innerHTML+=h;
  card.append($('p','fineprint','Latest reported quarter per issuer; periods may differ \\u00b7 ROE = n/m when capital structure (e.g. buybacks) distorts it \\u00b7 US issuers (SEC XBRL).'));
  return card;
}
function marketContextCard(){
  const M=MARKET; if(!M||(!M.rates&&!(M.positioning||[]).length&&!M.macro)) return null;
  const card=$('div','card');card.append($('h3',null,'Market psychology \\u2014 as of '+esc(M.as_of||'')));
  const r=M.rates;
  if(r){
    const sp=v=>v==null?'\\u2014':(v>=0?'+':'')+v.toFixed(2);
    const pc=v=>v==null?'\\u2014':v.toFixed(2)+'%';
    const inv=(r.spread_10y_2y!=null&&r.spread_10y_2y<0);
    const pl=$('div','priceline');
    pl.innerHTML='<b>Rate regime</b> 3M '+pc(r.y3m)+' \\u00b7 2Y '+pc(r.y2)+' \\u00b7 10Y '+pc(r.y10)+' \\u00b7 30Y '+pc(r.y30)
      +' \\u00b7 10Y\\u20132Y <span class="'+(inv?'down':'up')+'">'+sp(r.spread_10y_2y)+'</span> ('+esc(r.curve||'')+')'
      +(r.real10!=null?' \\u00b7 real 10Y '+pc(r.real10):'')
      +(r.breakeven10!=null?' \\u00b7 breakeven '+pc(r.breakeven10):'');
    card.append(pl);
  }
  if((M.positioning||[]).length){
    card.append($('div','subh','Cross-asset positioning \\u2014 CFTC CoT (speculative net \\u00b7 3y percentile)'));
    let h='<table><tr><th>Market</th><th class="num">Net (spec)</th><th class="num">WoW</th><th class="num">3y %ile</th><th>signal</th></tr>';
    M.positioning.forEach(p=>{
      const nc=p.net>=0?'up':'down', wc=p.wow>=0?'up':'down';
      const flag=p.extreme?'<span class="tag">'+esc(p.extreme)+'</span>':'';
      h+='<tr><td><b>'+esc(p.market)+'</b> <span class="conf">'+esc(p.who)+'</span></td>'
        +'<td class="num '+nc+'">'+(p.net>=0?'+':'')+Math.round(p.net).toLocaleString()+'</td>'
        +'<td class="num '+wc+'">'+(p.wow>=0?'+':'')+Math.round(p.wow).toLocaleString()+'</td>'
        +'<td class="num">'+(p.pctile==null?'\\u2014':p.pctile+'%')+'</td>'
        +'<td>'+flag+'</td></tr>';
    });
    h+='</table>';card.innerHTML+=h;
  }
  if((M.regime||[]).length){
    card.append($('div','subh','Regime read'));
    const ul=$('ul','list');M.regime.forEach(s=>{const li=$('li');li.innerHTML=esc(s);ul.append(li);});card.append(ul);
  }
  if(M.macro){
    const m=M.macro;
    card.append($('div','subh','Macro band \\u2014 FRED'));
    const grid=$('div','statgrid');
    const stat=(l,v)=>{const s=$('div','stat');s.append($('b',null,v),$('span',null,l));return s;};
    const fmt=o=>o==null?null:(o.value+(o.unit||''));
    [['VIX',m.vix],['HY spread',m.hy_spread],['S&P 500',m.spx],['Nasdaq',m.nasdaq],['US dollar',m.dollar],['Fin conditions',m.nfci],['Fed funds',m.fed_funds],['Unemployment',m.unrate]].forEach(([l,o])=>{const v=fmt(o);if(v!=null)grid.append(stat(l,v));});
    card.append(grid);
  }
  card.append($('p','fineprint','Market-wide context (not security-specific). '+esc(M.out_of_reach||'')));
  return card;
}
function render(p){ return p.language==='ko' ? renderKO(p) : renderEN(p); }

function renderEN(p){
  const box=document.getElementById('pack');box.innerHTML='';
  box.append($('h2','name',esc(p.name)+' <span style="color:var(--muted);font-weight:600">('+esc(p.ticker)+')</span>'));
  box.append($('p','meta',[p.exchanges.join(', '),esc(p.industry),'CIK '+esc(p.cik)].filter(Boolean).join(' \\u00b7 ')));
  if(p.search_note){box.append($('div','searchnote',esc(p.search_note)));}

  const t=p.trend||[];const last=t[t.length-1];
  const chips=$('div','chips');
  if(p.price){const c=$('div','chip');c.append($('b',null,'$'+p.price.close),$('span',null,'last close '+p.price.date+' (demo)'));chips.append(c);}
  if(last){
    [['Revenue',usd(last.revenue)],['Rev YoY',pct(last.revenue_yoy_pct,true)],['Gross margin',pct(last.gross_margin)],['Diluted EPS',last.eps_diluted!=null?'$'+last.eps_diluted.toFixed(2):'\\u2014']].forEach(([s,v])=>{const c=$('div','chip');c.append($('b',null,v),$('span',null,s+' \\u00b7 '+esc(last.period)));chips.append(c);});
  }
  box.append(chips);

  {const mc=marketContextCard(); if(mc)box.append(mc);}

  if(t.length){
    const card=$('div','card');card.append($('h3',null,'Financial trend (quarterly, SEC XBRL)'));
    let h='<table><tr><th>Period</th><th class="num">Revenue</th><th class="num">Rev YoY</th><th class="num">Gross %</th><th class="num">Oper %</th><th class="num">Net %</th><th class="num">Diluted EPS</th></tr>';
    t.forEach(r=>{const y=r.revenue_yoy_pct;h+='<tr><td>'+esc(r.period)+'</td><td class="num">'+usd(r.revenue)+'</td><td class="num '+(y==null?'':y>=0?'up':'down')+'">'+pct(y,true)+'</td><td class="num">'+pct(r.gross_margin)+'</td><td class="num">'+pct(r.operating_margin)+'</td><td class="num">'+pct(r.net_margin)+'</td><td class="num">'+(r.eps_diluted!=null?'$'+r.eps_diluted.toFixed(2):'\\u2014')+'</td></tr>';});
    h+='</table>';card.innerHTML+=h;box.append(card);
  }

  {const vc=valuationCard(p); if(vc)box.append(vc);}
  {const qf=qualityCard(p); if(qf)box.append(qf);}
  {const pcomp=peerCard(p); if(pcomp)box.append(pcomp);}

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

  {const qc=qualitativeCard(p); if(qc)box.append(qc);}
  {const rc=riskDeltaCard(p); if(rc)box.append(rc);}
  {const oc=ownershipCard(p); if(oc)box.append(oc);}
  {const cc=coverageCard(p); if(cc)box.append(cc);}

  if((p.sources||[]).length){const card=$('div','card');card.append($('h3',null,'Sources'));const ul=$('ul','list');p.sources.forEach(s=>{const li=$('li');const m=String(s).match(/(https?:\\/\\/\\S+)/);li.innerHTML=m?esc(s.replace(m[1],''))+'<a href="'+esc(m[1])+'" target="_blank" rel="noopener">'+esc(m[1])+'</a>':esc(s);ul.append(li);});card.append(ul);box.append(card);}
}

function renderKO(p){
  const box=document.getElementById('pack');box.innerHTML='';
  box.append($('h2','name',esc(p.name)+' <span style="color:var(--muted);font-weight:600">('+esc(p.ticker)+')</span>'));
  box.append($('p','meta',['KRX',esc(p.name_eng),'DART '+esc(p.cik)].filter(Boolean).join(' \\u00b7 ')));
  if(p.search_note){box.append($('div','searchnote',esc(p.search_note)));}

  const t=p.trend||[];const last=t[t.length-1];
  const chips=$('div','chips');
  if(last){
    [['매출액',won(last.revenue)],['매출 성장(YoY)',pct(last.revenue_yoy_pct,true)],['영업이익률',pct(last.operating_margin)],['순이익률',pct(last.net_margin)]].forEach(([s,v])=>{const c=$('div','chip');c.append($('b',null,v),$('span',null,s+' \\u00b7 '+esc(last.period)));chips.append(c);});
  }
  box.append(chips);

  {const mc=marketContextCard(); if(mc)box.append(mc);}

  if(t.length){
    const card=$('div','card');card.append($('h3',null,'재무 추이 (연간, DART 정기보고서)'));
    let h='<table><tr><th>기수</th><th class="num">매출액</th><th class="num">매출 성장</th><th class="num">매출총이익률</th><th class="num">영업이익률</th><th class="num">순이익률</th></tr>';
    t.forEach(r=>{const y=r.revenue_yoy_pct;h+='<tr><td>'+esc(r.period)+'</td><td class="num">'+won(r.revenue)+'</td><td class="num '+(y==null?'':y>=0?'up':'down')+'">'+pct(y,true)+'</td><td class="num">'+pct(r.gross_margin)+'</td><td class="num">'+pct(r.operating_margin)+'</td><td class="num">'+pct(r.net_margin)+'</td></tr>';});
    h+='</table>';card.innerHTML+=h;box.append(card);
  }

  if((p.disclosures||[]).length){
    const card=$('div','card');card.append($('h3',null,'공시 (정기보고서)'));
    const ul=$('ul','list');p.disclosures.forEach(d=>{const li=$('li');li.innerHTML='<a href="'+esc(d.url)+'" target="_blank" rel="noopener">'+esc(d.report_nm)+'</a> \\u00b7 접수 '+esc(d.rcept_dt)+(d.flr_nm?' \\u00b7 '+esc(d.flr_nm):'');ul.append(li);});card.append(ul);box.append(card);
  }

  const nc=$('div','card');nc.append($('h3',null,'뉴스 & 촉매 \\u2014 헤드라인 + 링크만'));
  if((p.news||[]).length){const ul=$('ul','list');p.news.forEach(n=>{const meta=[n.source,n.date].filter(Boolean).join(' \\u00b7 ');const li=$('li');li.innerHTML='<a href="'+esc(n.url)+'" target="_blank" rel="noopener">'+esc(n.headline)+'</a>'+(meta?' <span class="tag">'+esc(meta)+'</span>':'');ul.append(li);});nc.append(ul);}
  else nc.append($('p',null,'<span style="color:var(--muted)">캐시된 헤드라인 없음.</span>'));
  box.append(nc);

  if((p.sources||[]).length){const card=$('div','card');card.append($('h3',null,'출처'));const ul=$('ul','list');p.sources.forEach(s=>{const li=$('li');const m=String(s).match(/(https?:\\/\\/\\S+)/);li.innerHTML=m?esc(s.replace(m[1],''))+'<a href="'+esc(m[1])+'" target="_blank" rel="noopener">'+esc(m[1])+'</a>':esc(s);ul.append(li);});card.append(ul);box.append(card);}
}

const _home=document.getElementById('home'),_result=document.getElementById('result');
function showHome(){_result.hidden=true;_home.hidden=false;document.title='Pivox Brief \\u2014 Research Pack';}
function showResultView(){_home.hidden=true;_result.hidden=false;window.scrollTo(0,0);}
function packByTicker(tk){tk=String(tk||'').toUpperCase();return DATA.find(p=>String(p.ticker).toUpperCase()===tk);}
// --- search: fetch any US ticker live from the serverless backend ---
const SEARCH_API=/^(localhost|127\\.)/.test(location.hostname)?'http://localhost:8800':(window.PIVOX_API_BASE||'');
async function liveSearch(t){
  const box=document.getElementById('pack');
  if(!SEARCH_API){box.innerHTML='<div class="searchnote">Live lookup needs the API deployed \\u2014 set <code>window.PIVOX_API_BASE</code> (see DEPLOY.md). Featured tickers work offline.</div>';return;}
  box.innerHTML='<p class="meta">Searching '+esc(t)+'\\u2026</p>';
  try{
    const r=await fetch(SEARCH_API+'/api/research?ticker='+encodeURIComponent(t));
    const d=await r.json();
    if(!r.ok){box.innerHTML='<div class="searchnote">'+esc((d&&d.error)||('HTTP '+r.status))+'</div>';return;}
    render(d);
  }catch(e){box.innerHTML='<div class="searchnote">Search failed: '+esc(e.message)+'</div>';}
}
function openTicker(tk,opts){
  opts=opts||{};const TK=String(tk||'').toUpperCase().trim();if(!TK)return;
  if(opts.push!==false)history.pushState({tk:TK},'','?ticker='+encodeURIComponent(TK));
  document.title=TK+' \\u2014 Pivox Brief';
  showResultView();
  const p=packByTicker(TK);
  if(p)render(p);else liveSearch(TK);
}
function buildExamples(){
  const el=document.getElementById('examples'); if(!el) return;
  el.innerHTML='<span class="lbl">try</span>';
  ['NVDA','AAPL','MU','005930','000660'].forEach(tk=>{const b=$('button','ex',esc(tk));b.onclick=()=>openTicker(tk);el.append(b);});
}
function route(){const tk=new URLSearchParams(location.search).get('ticker');if(tk)openTicker(tk,{push:false});else showHome();}
const _sf=document.getElementById('search');
if(_sf)_sf.addEventListener('submit',e=>{e.preventDefault();const v=document.getElementById('q').value.trim();if(v)openTicker(v);});
const _bk=document.getElementById('back');
if(_bk)_bk.addEventListener('click',e=>{e.preventDefault();history.pushState({},'',location.pathname);showHome();});
window.addEventListener('popstate',route);
buildExamples();
route();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
