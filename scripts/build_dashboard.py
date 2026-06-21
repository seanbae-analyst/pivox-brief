"""Build the static dashboard (PROJECT.md §8, dashboard) — $0, self-contained.

Reads the committed signals, runs the eval over verified golds, computes the
cross-company analysis, and writes a single self-contained docs/index.html with
the data inlined (so it works opened locally AND on GitHub Pages — no fetch/CORS).

    python scripts/build_dashboard.py
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.analysis import analyze  # noqa: E402
from engine.evaluation import (  # noqa: E402
    calibration,
    score_record,
    target_sentence,
    threshold_sweep,
)
from engine.schema import EarningsSignal  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"


def load_signals() -> list[EarningsSignal]:
    out = []
    for p in sorted(glob.glob(str(ROOT / "data" / "output" / "*.json"))):
        if p.endswith(".draft.json"):
            continue
        out.append(EarningsSignal.model_validate_json(Path(p).read_text(encoding="utf-8")))
    return out


def load_golds() -> dict:
    golds = {}
    for g in sorted(glob.glob(str(ROOT / "data" / "goldset" / "*.gold.json"))):
        d = json.loads(Path(g).read_text(encoding="utf-8"))
        if d.get("_verified"):
            golds[(d["ticker"], d["period"])] = d
    return golds


def build_data() -> dict:
    signals = load_signals()
    golds = load_golds()
    pairs = [(s, golds[(s.ticker, s.period)]) for s in signals if (s.ticker, s.period) in golds]

    eval_records = []
    for s, g in pairs:
        sc = score_record(s, g)
        eval_records.append({
            "ticker": s.ticker,
            "guidance_ok": sc.guidance_correct,
            "tone_ok": sc.tone_correct,
            "themes_f1": round(sc.themes_f1, 2),
            "metrics_acc": round(sc.metrics_accuracy, 2),
            "ratios_acc": round(sc.ratios_accuracy, 2),
            "ratios_total": sc.ratios_total,
            "overall": round(sc.overall, 2),
        })
    sweep = [
        {"tau": r.threshold, "auto_rate": round(r.auto_rate, 2),
         "auto_acc": round(r.auto_accuracy, 2), "review": round(r.review_burden, 2)}
        for r in (threshold_sweep(pairs) if pairs else [])
    ]
    calib = {
        dim: [{"lo": b.lo, "hi": b.hi, "n": b.n, "acc": round(b.accuracy, 2)}
              for b in (calibration(pairs, dim) if pairs else [])]
        for dim in ("metrics", "guidance", "tone", "themes")
    }
    headline = target_sentence(pairs) if pairs else "No verified goldset yet."

    intel = analyze(signals)
    signal_dicts = [{
        "ticker": s.ticker, "period": s.period, "call_date": s.call_date,
        "guidance": s.guidance_direction.value, "tone": s.management_tone.value,
        "themes": [t.value for t in s.key_themes], "risk_factors": s.risk_factors,
        "metrics": [{"name": m.name, "value_usd": m.value_usd, "yoy": m.yoy_pct, "qoq": m.qoq_pct}
                    for m in s.headline_metrics],
        "ratios": [{"name": r.name, "value": r.value, "unit": r.unit.value} for r in s.ratios],
        "confidence": {"metrics": s.confidence.metrics, "guidance": s.confidence.guidance,
                       "tone": s.confidence.tone, "themes": s.confidence.themes,
                       "min": round(s.confidence.min_dim(), 2)},
        "needs_review": s.needs_review,
    } for s in signals]

    return {
        "n": len(signals),
        "signals": signal_dicts,
        "eval": {"headline": headline, "records": eval_records, "sweep": sweep, "calibration": calib},
        "intel": {
            "headlines": intel.headlines,
            "theme_frequency": intel.theme_frequency,
            "guidance": intel.guidance,
            "tone": intel.tone,
            "revenue_growth": intel.revenue_growth,
            "gross_margin": intel.gross_margin,
            "review": list(intel.review),
        },
    }


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pivox Brief — Earnings Intelligence</title>
<style>
:root{--ink:#0f172a;--muted:#64748b;--line:#e6e8ec;--soft:#f8fafc;--accent:#0d9488;--up:#0d9488;--down:#dc2626;--flat:#64748b;--review:#b45309;--ok:#0d9488}
*{box-sizing:border-box}
body{margin:0;background:#fff;color:var(--ink);font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1000px;margin:0 auto;padding:28px 20px 64px}
h1{font-size:22px;margin:0 0 2px;letter-spacing:-.01em}
.sub{color:var(--muted);font-size:13px;margin:0 0 18px}
.chips{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:22px}
.chip{border:1px solid var(--line);border-radius:10px;padding:8px 12px;min-width:96px}
.chip b{display:block;font-size:18px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.chip span{color:var(--muted);font-size:11px}
.tabs{display:flex;gap:6px;border-bottom:1px solid var(--line);margin-bottom:20px}
.tab{appearance:none;background:none;border:0;border-bottom:2px solid transparent;color:var(--muted);font:600 14px sans-serif;padding:10px 4px;margin-right:14px;cursor:pointer}
.tab.on{color:var(--ink);border-color:var(--accent)}
.view{display:none}.view.on{display:block}
.card{border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:16px}
.card h3{margin:0 0 12px;font-size:13px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.03em}
td.num,th.num{text-align:right;font-family:ui-monospace,Menlo,monospace}
.bar{height:8px;border-radius:6px;background:var(--accent);min-width:2px}
.barrow{display:grid;grid-template-columns:130px 1fr 40px;gap:10px;align-items:center;margin:6px 0;font-size:12px}
.barrow .lbl{color:var(--ink)}.barrow .v{color:var(--muted);text-align:right;font-family:ui-monospace,Menlo,monospace}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:600}
.b-up{background:#ecfdf5;color:#047857}.b-down{background:#fef2f2;color:#b91c1c}.b-flat{background:#f1f5f9;color:#475569}
.b-rev{background:#fffbeb;color:#b45309}.b-ok{background:#ecfdf5;color:#047857}
.theme{display:inline-block;background:var(--soft);border:1px solid var(--line);border-radius:6px;padding:1px 7px;font-size:11px;margin:2px 3px 0 0;color:#334155}
.obs{margin:0;padding-left:18px}.obs li{margin:4px 0}
.co{border:1px solid var(--line);border-radius:12px;padding:14px}
.co .t{font-weight:700;font-size:15px}.co .p{color:var(--muted);font-size:11px;margin-bottom:8px}
.co .m{font-family:ui-monospace,Menlo,monospace;font-size:12px;color:#334155;margin:2px 0}
.foot{color:var(--muted);font-size:12px;margin-top:24px;border-top:1px solid var(--line);padding-top:14px}
.headline{font-size:15px;background:var(--soft);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin-bottom:16px}
.ok{color:var(--ok);font-weight:700}.x{color:var(--down);font-weight:700}
</style>
</head>
<body>
<div class="wrap">
<h1>Pivox Brief</h1>
<p class="sub">Earnings-call standardization &amp; intelligence — built for $0. Descriptive analysis, not investment advice.</p>
<div class="chips" id="chips"></div>
<div class="tabs">
<button class="tab on" data-v="intel">Earnings Intelligence</button>
<button class="tab" data-v="perf">System Performance</button>
</div>
<section class="view on" id="intel"></section>
<section class="view" id="perf"></section>
<div class="foot" id="foot"></div>
</div>
<script>
const DATA = __DATA__;
const $=(t,c,h)=>{const e=document.createElement(t);if(c)e.className=c;if(h!=null)e.innerHTML=h;return e;};
const usd=v=>{if(v==null)return '\\u2014';const a=Math.abs(v);if(a>=1e9)return '$'+(v/1e9).toFixed(1)+'B';if(a>=1e6)return '$'+(v/1e6).toFixed(0)+'M';return '$'+v.toLocaleString();};
const pct=v=>v==null?'':(v>=0?'+':'')+v.toFixed(0)+'%';
const gBadge=g=>({raised:['b-up','raised'],lowered:['b-down','lowered'],maintained:['b-flat','maintained'],not_given:['b-flat','none']}[g]||['b-flat',g]);

function chips(){
  const e=DATA.eval, objAcc=e.records.length?Math.round(100*e.records.reduce((a,r)=>a+(r.guidance_ok&&r.tone_ok&&r.metrics_acc>=0.99?1:0),0)/e.records.length):0;
  const rv=DATA.intel.review;
  const items=[['Companies',DATA.n],['Obj. accuracy',objAcc+'%'],['Review rate',Math.round(rv[2]*100)+'%'],['Cost','$0']];
  const box=document.getElementById('chips');
  items.forEach(([s,v])=>{const c=$('div','chip');c.append($('b',null,v),$('span',null,s));box.append(c);});
}

function bars(rows,fmt){
  const max=Math.max(1,...rows.map(r=>Math.abs(r[1])));
  const wrap=$('div');
  rows.forEach(([lbl,val])=>{
    const row=$('div','barrow');
    const bar=$('div','bar');bar.style.width=Math.max(2,Math.round(100*Math.abs(val)/max))+'%';
    row.append($('div','lbl',lbl),(()=>{const h=$('div');h.append(bar);return h;})(),$('div','v',fmt?fmt(val):val));
    wrap.append(row);
  });
  return wrap;
}

function renderIntel(){
  const v=document.getElementById('intel');v.innerHTML='';
  const obs=$('div','card');obs.append($('h3',null,'Observations'));
  const ul=$('ul','obs');DATA.intel.headlines.forEach(h=>ul.append($('li',null,h)));obs.append(ul);v.append(obs);

  const two=$('div','grid');two.style.gridTemplateColumns='1fr 1fr';
  const tc=$('div','card');tc.append($('h3',null,'Theme frequency'));
  tc.append(bars(DATA.intel.theme_frequency,x=>x));two.append(tc);
  const gc=$('div','card');gc.append($('h3',null,'Guidance &amp; tone'));
  gc.append($('div',null,'<b style="font-size:12px">Guidance</b>'));
  gc.append(bars(Object.entries(DATA.intel.guidance),x=>x));
  gc.append($('div',null,'<b style="font-size:12px">Tone</b>'));
  gc.append(bars(Object.entries(DATA.intel.tone),x=>x));two.append(gc);
  v.append(two);

  const rg=$('div','card');rg.append($('h3',null,'Revenue growth (YoY)'));
  rg.append(bars(DATA.intel.revenue_growth,pct));v.append(rg);

  if((DATA.intel.gross_margin||[]).length){const gm=$('div','card');gm.append($('h3',null,'Gross margin (where disclosed)'));gm.append(bars(DATA.intel.gross_margin,x=>x.toFixed(1)+'%'));v.append(gm);}

  const co=$('div','card');co.append($('h3',null,'Companies'));
  const grid=$('div','grid');
  DATA.signals.forEach(s=>{
    const c=$('div','co');
    c.append($('div','t',s.ticker),$('div','p',s.period+' &middot; '+s.call_date));
    const gb=gBadge(s.guidance);
    const badges=$('div');badges.style.margin='0 0 8px';
    badges.append($('span','badge '+gb[0],'guidance: '+gb[1]),document.createTextNode(' '),$('span','badge b-flat',s.tone));
    if(s.needs_review)badges.append(document.createTextNode(' '),$('span','badge b-rev','review'));
    else badges.append(document.createTextNode(' '),$('span','badge b-ok','auto'));
    c.append(badges);
    const rev=s.metrics.find(m=>m.name==='total_revenue');
    if(rev)c.append($('div','m','revenue '+usd(rev.value_usd)+' '+pct(rev.yoy)));
    (s.ratios||[]).forEach(r=>c.append($('div','m',r.name.replace(/_/g,' ')+' '+(r.unit==='percent'?r.value.toFixed(1)+'%':'$'+r.value.toFixed(2)))));
    const th=$('div');s.themes.forEach(t=>th.append($('span','theme',t)));c.append(th);
    grid.append(c);
  });
  co.append(grid);v.append(co);
}

function renderPerf(){
  const v=document.getElementById('perf');v.innerHTML='';const e=DATA.eval;
  v.append($('div','headline',e.headline));

  const ac=$('div','card');ac.append($('h3',null,'Per-record accuracy (vs verified goldset)'));
  let h='<table><tr><th>Ticker</th><th>Guidance</th><th>Tone</th><th class="num">Themes F1</th><th class="num">Metrics</th><th class="num">Ratios</th><th class="num">Overall</th></tr>';
  e.records.forEach(r=>{h+=`<tr><td>${r.ticker}</td><td class="${r.guidance_ok?'ok':'x'}">${r.guidance_ok?'\\u2713':'\\u2717'}</td><td class="${r.tone_ok?'ok':'x'}">${r.tone_ok?'\\u2713':'\\u2717'}</td><td class="num">${r.themes_f1.toFixed(2)}</td><td class="num">${r.metrics_acc.toFixed(2)}</td><td class="num">${r.ratios_total?r.ratios_acc.toFixed(2):'\\u2014'}</td><td class="num">${r.overall.toFixed(2)}</td></tr>`;});
  h+='</table>';ac.innerHTML+=h;v.append(ac);

  const sc=$('div','card');sc.append($('h3',null,'Threshold sweep (auto-approve at min-confidence \\u2265 \\u03c4)'));
  let s='<table><tr><th class="num">\\u03c4</th><th class="num">Auto-processed</th><th class="num">Accuracy (auto)</th><th class="num">Review burden</th></tr>';
  e.sweep.forEach(r=>{s+=`<tr><td class="num">${r.tau}</td><td class="num">${Math.round(r.auto_rate*100)}%</td><td class="num">${r.auto_acc.toFixed(2)}</td><td class="num">${Math.round(r.review*100)}%</td></tr>`;});
  s+='</table>';sc.innerHTML+=s;v.append(sc);

  const cc=$('div','card');cc.append($('h3',null,'Calibration (confidence band \\u2192 observed accuracy)'));
  let c='<table><tr><th>Dimension</th><th>Bands</th></tr>';
  Object.entries(e.calibration).forEach(([dim,bs])=>{const cells=bs.map(b=>`[${b.lo.toFixed(2)}\\u2013${b.hi.toFixed(2)}] ${Math.round(b.acc*100)}% (n${b.n})`).join('&nbsp;&nbsp; ');c+=`<tr><td>${dim}</td><td style="font-family:ui-monospace,Menlo,monospace;font-size:12px">${cells||'\\u2014'}</td></tr>`;});
  c+='</table>';cc.innerHTML+=c;v.append(cc);
}

document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));
  document.querySelectorAll('.view').forEach(x=>x.classList.remove('on'));
  t.classList.add('on');document.getElementById(t.dataset.v).classList.add('on');
});

chips();renderIntel();renderPerf();
document.getElementById('foot').innerHTML='n='+DATA.n+' \\u2014 illustrative, not statistical. Goldset is single-annotator (themes = intra-annotator). 3/4 transcripts are condensed sources. Built for $0 by build_dashboard.py. See CASE_STUDY.md.';
</script>
</body>
</html>
"""


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    data = build_data()
    html = TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    out = DOCS / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"Built {out}  ({len(html):,} bytes, {data['n']} companies)")


if __name__ == "__main__":
    main()
