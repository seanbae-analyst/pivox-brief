"""Beginner glossary — turns the brief into a teacher. Plain-Korean explanations for every
piece of jargon, an analogy where it helps, and a deterministic 'term of the day' so a 주린이
learns one concept per morning without it ever feeling random.

- gloss(term)       → short inline parenthetical (e.g. "공포지수, 높을수록 시장이 무서워함")
- explain(term)     → full {gloss, long, analogy}
- term_of_day(date) → deterministic pick (stable per calendar day, rotates through the deck)
"""
from __future__ import annotations

# term → (short gloss, long explanation, analogy or "")
GLOSSARY: dict[str, tuple[str, str, str]] = {
    "위험회피": (
        "투자자들이 겁먹고 안전자산으로 도망가는 것",
        "주식·코인처럼 위험한 자산을 팔고 현금·금·국채 같은 안전한 곳으로 돈을 옮기는 분위기. '리스크 오프(Risk-off)'라고도 해요.",
        "비 온다는 예보에 다들 우산 챙기고 외출 줄이는 것과 비슷해요.",
    ),
    "위험선호": (
        "투자자들이 자신감 있게 위험을 감수하는 것",
        "주식·코인 같은 위험자산에 적극적으로 돈을 넣는 분위기. '리스크 온(Risk-on)'.",
        "날씨 좋을 때 다들 나들이 가는 것처럼요.",
    ),
    "VIX": (
        "공포지수 — 높을수록 시장이 무서워함",
        "미국 시장이 앞으로 얼마나 출렁일지에 대한 불안의 크기. 보통 20 아래면 평온, 30 넘으면 공포 구간.",
        "시장의 '심박수'예요. 평소엔 잔잔하다 겁먹으면 확 뛰죠.",
    ),
    "크레딧 스프레드": (
        "위험한 기업이 돈 빌릴 때 더 내는 이자, 벌어지면 불안 신호",
        "신용도 낮은 기업의 채권 금리와 안전한 국채 금리의 차이. 이 차이가 벌어지면 '돈 빌려주기 무섭다'는 뜻 — 경기·신용 불안의 신호.",
        "은행이 불안한 사람한테 더 높은 이자를 받는 것과 같아요. 그 이자가 오르면 분위기가 나빠진다는 신호.",
    ),
    "변동성": (
        "가격이 얼마나 출렁이는지",
        "위아래 흔들림의 크기. 변동성이 커지면 하루에도 크게 오르내려서 불안해져요.",
        "잔잔한 호수 vs 파도치는 바다의 차이예요.",
    ),
    "수익률 커브": (
        "단기 금리와 장기 금리의 모양",
        "보통은 먼 미래(10년) 금리가 가까운 미래(2년)보다 높아요(정상). 거꾸로 뒤집히면(역전) 경기침체 걱정의 신호로 봐요.",
        "'내일보다 한 달 뒤가 더 춥다'는 이상한 일기예보 — 뭔가 잘못됐다는 경고죠.",
    ),
    "breakeven": (
        "시장이 예상하는 미래 물가(인플레이션)",
        "채권 가격에 녹아있는 '앞으로 물가가 이만큼 오를 것'이라는 시장의 기대치.",
        "",
    ),
    "포지셔닝": (
        "큰손들이 지금 어느 쪽에 베팅해뒀는지",
        "헤지펀드·기관이 오를 쪽(롱)에 걸었는지 내릴 쪽(숏)에 걸었는지. 한쪽으로 너무 쏠리면 반대로 출렁이기 쉬워요.",
        "시소 한쪽에 다 몰려 타면 갑자기 뒤집히는 것과 같아요.",
    ),
    "원화 약세": (
        "원/달러 환율이 올라 원화 가치가 떨어진 것",
        "1달러를 사는 데 더 많은 원이 필요해진 상태. 보통 외국인이 한국 주식을 팔 때 같이 나타나요.",
        "",
    ),
    "섹터 로테이션": (
        "돈이 한 업종에서 다른 업종으로 옮겨가는 것",
        "예를 들어 2차전지에서 빠진 돈이 반도체로 들어가는 흐름. 시장이 어디에 베팅하는지 보여줘요.",
        "",
    ),
    "시장 폭": (
        "얼마나 '많은' 종목이 오르고 있는지",
        "지수는 몇몇 대형주가 끌어올릴 수 있어요. 시장 폭은 실제로 많은 종목이 오르는지(50일선 위인지) 봐요. 폭이 좁으면 소수만 오르는 약한 장.",
        "혼자 뛰는 응원단원 한 명 vs 관중 전체가 일어선 것의 차이예요.",
    ),
    "안전자산 선호": (
        "겁날 때 주식 팔고 안전한 국채로 가는 정도",
        "불안하면 투자자는 주식을 팔고 안전한 국채를 사요. 주식이 채권보다 잘 나가면 자신감(탐욕), 채권이 이기면 몸 사림(공포).",
        "소풍 갈지(주식) 집에 있을지(채권) 고르는 거예요 — 날씨가 불안하면 집에 있죠.",
    ),
    "공포탐욕지수": (
        "시장 전체 분위기를 0~100 한 숫자로",
        "여러 심리 신호(주가·변동성·신용·시장폭 등)를 합쳐 0(극단적 공포)~100(극단적 탐욕)으로 나타낸 거예요. 낮으면 다들 겁먹은 것.",
        "시장의 '기분 온도계'예요.",
    ),
}

# the 'term of the day' rotates through this curated deck (terms with a good analogy)
_DECK = ["위험회피", "VIX", "크레딧 스프레드", "수익률 커브", "포지셔닝", "변동성",
         "위험선호", "섹터 로테이션", "시장 폭", "안전자산 선호", "공포탐욕지수"]


def gloss(term: str) -> str | None:
    g = GLOSSARY.get(term)
    return g[0] if g else None


def explain(term: str) -> dict | None:
    g = GLOSSARY.get(term)
    if not g:
        return None
    return {"term": term, "gloss": g[0], "long": g[1], "analogy": g[2]}


def glosses_for(terms: list[str]) -> list[dict]:
    out = []
    for t in terms:
        g = GLOSSARY.get(t)
        if g:
            out.append({"term": t, "gloss": g[0]})
    return out


def term_of_day(date_str: str) -> dict:
    """Deterministic by calendar day — same day → same term, no randomness needed."""
    digits = "".join(ch for ch in date_str if ch.isdigit()) or "0"
    idx = int(digits) % len(_DECK)
    return explain(_DECK[idx])


# 5-step mood thermometer — turns the numbers into one feeling a beginner gets instantly
_MOODS = [
    ("😎", "안심", "시장이 차분해요"),
    ("😐", "보통", "특별한 긴장은 없어요"),
    ("😟", "주의", "슬슬 경계 분위기예요"),
    ("😨", "불안", "투자자들이 겁먹고 있어요"),
    ("😱", "공포", "강한 공포 — 크게 출렁이는 구간"),
]


def mood(flow: dict, rates: dict | None) -> dict:
    """Fear score (0=calm … high=fear) from the cleanest daily signals → a 1–5 level."""
    by = {f["label"]: f for f in (flow or {}).values()} if isinstance(flow, dict) else {f["label"]: f for f in (flow or [])}
    score = 0
    spx = by.get("S&P 500")
    if spx and spx.get("chg5_pct") is not None:
        if spx["chg5_pct"] < -3:
            score += 2
        elif spx["chg5_pct"] < 0:
            score += 1
    vix = by.get("VIX")
    if vix and vix.get("value") is not None:
        if vix["value"] >= 28:
            score += 2
        elif vix["value"] >= 19:
            score += 1
        if (vix.get("chg5") or 0) > 0:
            score += 1
    hy = by.get("HY spread")
    if hy and (hy.get("chg5_bp") or 0) > 0:
        score += 1
    level = max(1, min(5, score + 1))  # 1..5
    emoji, label, note = _MOODS[level - 1]
    return {"level": level, "emoji": emoji, "label": label, "note": note}
