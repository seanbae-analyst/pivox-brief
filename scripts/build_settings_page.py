#!/usr/bin/env python3
"""Generate docs/settings.html — the public picker page where you choose themes / 초보 level /
custom tickers. Saves to Supabase (anon key) so the morning cron (engine/watchlist.py) reads it.

The Supabase URL + anon key are baked in from env at build time (anon keys are public by design;
this is a personal single-row settings table). Without env, the page still renders but shows a
'설정 필요' notice and disables save. Run by refresh_and_deploy.sh before deploy.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.themes import THEMES  # noqa: E402
from engine.watchlist import DEFAULT  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "docs" / "settings.html"

themes_js = json.dumps(
    [{"key": k, "label": v["label"], "names": [n for n, _ in v["tickers"]]} for k, v in THEMES.items()],
    ensure_ascii=False,
)
cfg = json.dumps({
    "url": (os.environ.get("SUPABASE_URL") or "").rstrip("/"),
    "key": os.environ.get("SUPABASE_ANON_KEY") or "",
    "default": DEFAULT,
}, ensure_ascii=False)

HTML = """<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>브리핑 설정 — 내가 보고 싶은 것 고르기</title>
<style>
:root{--ink:#15171c;--sub:#5b6470;--line:#e6e8ec;--bg:#eef0f3;--card:#fff;--accent:#1f6feb}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.55 -apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo','Malgun Gothic',sans-serif}
.wrap{max-width:600px;margin:0 auto;padding:20px 14px 60px}
h1{font-size:22px;margin:0 0 2px;letter-spacing:-.4px}.sub{color:var(--sub);font-size:13px;margin:0 0 18px}
.sec{font-size:13px;font-weight:800;color:var(--ink);margin:22px 2px 8px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.t{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:11px 12px;cursor:pointer;display:flex;gap:9px;align-items:flex-start}
.t.on{border-color:var(--accent);background:#eef3fb}
.t input{margin:3px 0 0}.t .l{font-weight:700;font-size:14px}.t .n{color:var(--sub);font-size:11px;margin-top:2px;line-height:1.4}
.lv{display:flex;gap:8px}.lv button{flex:1;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:11px;font-size:14px;font-weight:700;color:var(--sub);cursor:pointer}
.lv button.on{border-color:var(--accent);background:#eef3fb;color:var(--accent)}
input.tx{width:100%;border:1px solid var(--line);border-radius:10px;padding:11px 12px;font-size:14px}
.save{margin-top:22px;width:100%;background:var(--accent);color:#fff;border:0;border-radius:12px;padding:14px;font-size:16px;font-weight:800;cursor:pointer}
.save:disabled{background:#9bb6e0}
.msg{text-align:center;font-size:13px;margin-top:10px;min-height:18px}
.warn{background:#fdf6e3;border:1px solid #f0e0b0;border-radius:10px;padding:11px 13px;font-size:13px;color:#7a5c10;margin-bottom:14px}
a{color:var(--accent)}.nav{font-size:12px;margin-bottom:6px}
</style></head><body><div class="wrap">
<div class="nav"><a href="/brief.html">← 오늘 브리핑</a></div>
<h1>브리핑 설정</h1><p class="sub">내가 보고 싶은 테마·종목·설명 수준을 고르면 내일 아침 브리핑부터 반영돼요.</p>
<div id="warn" class="warn" style="display:none">⚠️ 아직 저장소(Supabase)가 연결 안 됐어요. 고른 건 이 브라우저에만 임시 저장돼요.</div>
<div class="sec">📌 테마 (보고 싶은 것 체크)</div>
<div id="themes" class="grid"></div>
<div class="sec">📖 설명 수준</div>
<div class="lv" id="levels"></div>
<div class="sec">➕ 내 종목 직접 추가 (쉼표로, 예: TSLA, 005930.KS)</div>
<input class="tx" id="custom" placeholder="비워둬도 돼요">
<button class="save" id="save">저장하기</button>
<div class="msg" id="msg"></div>
</div>
<script>
const CFG = __CFG__, THEMES = __THEMES__;
const LEVELS = ["초보","보통","고수"];
let sel = new Set(CFG.default.themes), level = CFG.default.explain_level;
const live = CFG.url && CFG.key;
if(!live) document.getElementById('warn').style.display='block';

function renderThemes(){
  document.getElementById('themes').innerHTML = THEMES.map(t=>
    `<label class="t ${sel.has(t.key)?'on':''}" data-k="${t.key}">
      <input type="checkbox" ${sel.has(t.key)?'checked':''}>
      <span><span class="l">${t.label}</span><span class="n">${t.names.slice(0,4).join(', ')}</span></span>
    </label>`).join('');
  document.querySelectorAll('.t').forEach(el=>el.onclick=e=>{
    if(e.target.tagName!=='INPUT'){const c=el.querySelector('input');c.checked=!c.checked;}
    const k=el.dataset.k; const c=el.querySelector('input');
    c.checked?sel.add(k):sel.delete(k); el.classList.toggle('on',c.checked);
  });
}
function renderLevels(){
  document.getElementById('levels').innerHTML = LEVELS.map(l=>
    `<button data-l="${l}" class="${l===level?'on':''}">${l}</button>`).join('');
  document.querySelectorAll('#levels button').forEach(b=>b.onclick=()=>{
    level=b.dataset.l; renderLevels();
  });
}
async function loadCurrent(){
  if(live){
    try{
      const r=await fetch(`${CFG.url}/rest/v1/brief_settings?id=eq.default&select=*`,
        {headers:{apikey:CFG.key,Authorization:'Bearer '+CFG.key}});
      const rows=await r.json();
      if(rows&&rows[0]){sel=new Set(rows[0].themes||[]);level=rows[0].explain_level||level;
        document.getElementById('custom').value=(rows[0].custom||[]).join(', ');}
    }catch(e){}
  }else{
    try{const s=JSON.parse(localStorage.getItem('pivox_wl')||'null');
      if(s){sel=new Set(s.themes);level=s.explain_level;document.getElementById('custom').value=(s.custom||[]).join(', ');}}catch(e){}
  }
  renderThemes();renderLevels();
}
document.getElementById('save').onclick=async()=>{
  const custom=document.getElementById('custom').value.split(',').map(s=>s.trim()).filter(Boolean);
  const body={id:'default',themes:[...sel],custom,explain_level:level};
  const msg=document.getElementById('msg');
  if(!sel.size){msg.textContent='테마를 최소 1개는 골라주세요.';return;}
  if(live){
    msg.textContent='저장 중…';
    try{
      const r=await fetch(`${CFG.url}/rest/v1/brief_settings`,{method:'POST',
        headers:{apikey:CFG.key,Authorization:'Bearer '+CFG.key,'Content-Type':'application/json',Prefer:'resolution=merge-duplicates'},
        body:JSON.stringify(body)});
      msg.textContent = r.ok ? '✅ 저장됐어요! 내일 아침 브리핑부터 반영돼요.' : '저장 실패 ('+r.status+')';
    }catch(e){msg.textContent='저장 실패: '+e;}
  }else{
    localStorage.setItem('pivox_wl',JSON.stringify(body));
    msg.textContent='✅ 이 브라우저에 임시 저장됨 (Supabase 연결 시 자동 반영).';
  }
};
loadCurrent();
</script></body></html>"""

OUT.write_text(HTML.replace("__CFG__", cfg).replace("__THEMES__", themes_js), encoding="utf-8")
print(f"wrote {OUT}  (supabase={'on' if os.environ.get('SUPABASE_URL') else 'off'})")
