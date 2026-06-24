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
from engine.research_pack import build_us_pack, coverage_manifest, earnings_read  # noqa: E402

load_dotenv()  # EDGAR_USER_AGENT / DART_API_KEY from .env

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
        "quant": pack.quant,
        "qualitative": pack.qualitative,
        "ownership": pack.ownership,
        "coverage": coverage_manifest(pack),
        "sources": pack.sources,
    }


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
            packs.append(pack_to_dict(us))
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
.statgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(132px,1fr));gap:9px}
.stat{border:1px solid var(--line);border-radius:8px;padding:8px 10px}
.stat b{display:block;font-size:15px;font-family:ui-monospace,Menlo,monospace}
.stat span{color:var(--muted);font-size:11px}
.priceline{margin-top:12px;font-size:12px;color:#334155;font-family:ui-monospace,Menlo,monospace;line-height:1.8}
.conf{color:var(--muted);font-size:11px}
.subh{font-weight:700;font-size:12px;margin:12px 0 4px}
.fineprint{color:var(--muted);font-size:11px;margin-top:10px}
.covrow{padding:7px 0;font-size:12px;border-bottom:1px solid var(--line);line-height:1.7}
.covrow:last-child{border:0}
.covlabel{font-weight:700;margin-right:6px;white-space:nowrap}
.cov-ok{color:var(--up)}.cov-mid{color:#b45309}.cov-out{color:var(--down)}
</style>
</head>
<body>
<div class="wrap">
<h1>Pivox Brief — Research Pack</h1>
<p class="sub">One page of price-relevant factors from official filings — SEC EDGAR (US) &amp; Open DART (KR). A research starting point — not investment advice.</p>
<div class="sel" id="sel"></div>
<div id="pack"></div>
<div class="foot">US: SEC EDGAR (XBRL) · KR: Open DART · prices = demo only · news = headlines + links only · built for $0. Descriptive analysis, not investment advice / 투자자문이 아닙니다.</div>
</div>
<script>
const DATA = __DATA__;
const $=(t,c,h)=>{const e=document.createElement(t);if(c)e.className=c;if(h!=null)e.innerHTML=h;return e;};
const usd=v=>{if(v==null)return '\\u2014';const a=Math.abs(v);if(a>=1e9)return '$'+(v/1e9).toFixed(2)+'B';if(a>=1e6)return '$'+(v/1e6).toFixed(0)+'M';return '$'+v.toLocaleString();};
const pct=(v,s)=>v==null?'\\u2014':(s&&v>=0?'+':'')+v.toFixed(1)+'%';
const won=v=>{if(v==null)return '\\u2014';const a=Math.abs(v);if(a>=1e12)return (v/1e12).toFixed(1)+'조원';if(a>=1e8)return Math.round(v/1e8)+'억원';return v.toLocaleString()+'원';};
const esc=s=>(s==null?'':String(s)).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const conf=c=>c==null?'':' <span class="conf">conf '+c+'</span>';
const mult=v=>v==null?'\\u2014':v+'\\u00d7';

function valuationCard(p){
  const q=p.quant; if(!q) return null;
  const v=q.valuation||{},pr=q.profitability||{},h=q.health||{},c=q.capital_return||{},px=q.price||{};
  const card=$('div','card');card.append($('h3',null,'Valuation & quality'));
  const grid=$('div','statgrid');
  const stat=(label,val)=>{const s=$('div','stat');s.append($('b',null,val),$('span',null,label));return s;};
  const num=x=>x==null?'\\u2014':x;
  [['Market cap',usd(v.market_cap)],['P/E (TTM)',mult(v.pe_ttm)],['P/S',mult(v.ps_ttm)],['P/B',mult(v.pb)],['EV/EBITDA',mult(v.ev_ebitda)],
   ['FCF yield',pct(v.fcf_yield_pct)],['Div yield',pct(v.dividend_yield_pct)],['Buyback yield',pct(v.buyback_yield_pct)],['ROE',pct(pr.roe_pct)],
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

function fileRow(f){
  if(!f)return '';
  const lbl=(f.labels&&f.labels.length)?' \\u2014 '+esc(f.labels.join('; ')):'';
  return '<a href="'+esc(f.url)+'" target="_blank" rel="noopener">'+esc(f.primary_document||'filing')+'</a> \\u00b7 filed '+esc(f.filing_date)+lbl;
}

function render(p){ return p.language==='ko' ? renderKO(p) : renderEN(p); }

function renderEN(p){
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

  {const vc=valuationCard(p); if(vc)box.append(vc);}

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
  {const oc=ownershipCard(p); if(oc)box.append(oc);}
  {const cc=coverageCard(p); if(cc)box.append(cc);}

  if((p.sources||[]).length){const card=$('div','card');card.append($('h3',null,'Sources'));const ul=$('ul','list');p.sources.forEach(s=>{const li=$('li');const m=String(s).match(/(https?:\\/\\/\\S+)/);li.innerHTML=m?esc(s.replace(m[1],''))+'<a href="'+esc(m[1])+'" target="_blank" rel="noopener">'+esc(m[1])+'</a>':esc(s);ul.append(li);});card.append(ul);box.append(card);}
}

function renderKO(p){
  const box=document.getElementById('pack');box.innerHTML='';
  box.append($('h2','name',esc(p.name)+' <span style="color:var(--muted);font-weight:600">('+esc(p.ticker)+')</span>'));
  box.append($('p','meta',['KRX',esc(p.name_eng),'DART '+esc(p.cik)].filter(Boolean).join(' \\u00b7 ')));

  const t=p.trend||[];const last=t[t.length-1];
  const chips=$('div','chips');
  if(last){
    [['매출액',won(last.revenue)],['매출 성장(YoY)',pct(last.revenue_yoy_pct,true)],['영업이익률',pct(last.operating_margin)],['순이익률',pct(last.net_margin)]].forEach(([s,v])=>{const c=$('div','chip');c.append($('b',null,v),$('span',null,s+' \\u00b7 '+esc(last.period)));chips.append(c);});
  }
  box.append(chips);

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
