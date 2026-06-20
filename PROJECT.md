# PROJECT.md — Earnings Call Standardization Engine
> 흩어지고 긴 어닝콜 전사본을, 자기 확신을 아는 AI 파이프라인으로,
> **비교 가능한 표준 신호 데이터**로 바꾸는 엔진. 그리고 그게 얼마나 믿을 만한지 증명하는 것.
이 문서는 프로젝트의 단일 기준(source of truth)이다. 모든 빌드 결정은 여기에 맞춘다.
---
## 1. 문제 (Problem)
어닝콜 전사본은 회사마다 수십 페이지짜리 자유 텍스트다. 가이던스 방향, 경영진 톤, 반복되는
리스크/테마 — 정보는 다 있지만 **구조가 없어 비교가 불가능**하다. 워치리스트 N개 회사가
이번 분기에 어떻게 바뀌었는지 보려면 N개를 다 읽어야 한다. 손으로는 스케일이 안 나오고,
룰 기반은 회사마다 표현이 달라 깨진다.
**핵심 질문:** AI로 이걸 믿을 만하게 표준화할 수 있나? 그리고 더 중요하게 —
**못 믿을 때를 시스템이 스스로 알 수 있나?**
## 2. 최종 결과물 (Deliverable)
**"워치리스트 어닝 인텔리전스"** — 투자자/애널리스트가 전사본을 다 읽지 않고도
*"내 관심 종목 중 이번 분기에 가이던스나 톤이 바뀐 게 누구고, 왜?"* 에 답을 얻는 도구.
- 표준화 품질 = 제품 신뢰도 (둘은 같은 것). 그래서 eval은 장식이 아니라 근간.
- **진짜 최종 산출물은 대시보드가 아니라 케이스 스터디.** 시스템은 "진짜 만들었다"는 증거.
- 포지셔닝: **투자 신호("뭘 사라") 도구가 아니라 데이터 표준화·인텔리전스 도구.**
  (PM 포트폴리오로 정직하고 컴플라이언스 함정도 회피.)
## 3. 확정 스키마 (Schema v0) — "내가 정의한 표준"
```python
from pydantic import BaseModel
from enum import Enum
from typing import Optional
class GuidanceDirection(str, Enum):
    raised = "raised"; lowered = "lowered"
    maintained = "maintained"; not_given = "not_given"
class Tone(str, Enum):
    confident = "confident"; cautious = "cautious"
    defensive = "defensive"; mixed = "mixed"
class Metric(BaseModel):
    name: str                  # e.g. "total_revenue"
    value_usd: Optional[float]  # 단일 단위(USD)로 정규화
    yoy_pct: Optional[float]
    qoq_pct: Optional[float]
class Confidence(BaseModel):
    metrics: float; guidance: float
    tone: float; themes: float
class EarningsSignal(BaseModel):
    ticker: str
    period: str                # "Q1 FY2027"
    call_date: str             # ISO 8601
    headline_metrics: list[Metric]
    guidance_direction: GuidanceDirection
    guidance_detail: Optional[str]
    key_themes: list[str]      # 통제 어휘에서만 선택 (아래 §4)
    risk_factors: list[str]
    management_tone: Tone
    confidence: Confidence
    needs_review: bool         # confidence 임계값에서 파생
```
## 4. 통제 어휘 — key_themes 택소노미 (v0)
모델은 자유 텍스트를 아래 고정 목록의 가장 가까운 테마로 **매핑만** 한다. 자유 생성 금지.
```
demand_strength      demand_weakness      pricing_power        margin_expansion
margin_pressure      capex_investment     supply_constraint    new_product_ramp
market_share_gain    competitive_pressure cost_efficiency      M&A
regulatory_legal     macro_headwind       capital_return       segment_expansion
__other__   # escape hatch
```
- `__other__` 매핑 비율은 **택소노미 건강 지표**. 높으면 택소노미를 확장한다.
- eval 돌리며 항목 추가/병합. v0는 출발점일 뿐.
## 5. 확정된 정규화 결정 (Locked Decisions)
| # | 결정 | 선택 | 근거 |
|---|------|------|------|
| ① | 숫자 canonical | **보도자료 정밀값** (예: `81615000000`) | 콜 발언("$82B")은 검증용. 정밀도 우선. |
| ② | key_themes 방식 | **통제 어휘** (§4) | 워치리스트 전체 비교 가능 + eval에서 분류 정확도 측정 용이. |
| ③ | tone 자동승인 여부 | **보류 — eval 후 결정** | tone은 주관적이라 confidence가 낮게 나올 것. 데이터로 판단. |
## 6. 신뢰도 + Human-in-the-loop
- confidence 높음 → 자동 승인 / 낮음 → 사람 검토 큐.
- confidence 생성: ①모델 self-report ②검증 룰(값이 상식 범위/택소노미 내인가)
  ③**일관성 체크**(Haiku 2회 또는 Haiku vs Sonnet 비교, 불일치 시 low-confidence). ③이 가장 강한 신호.
- **임계값을 어디 두느냐 = 가장 중요한 PM 결정.** 답은 §7 eval이 제공.
## 7. Evaluation (포트폴리오의 심장)
- **골드셋:** 손으로 정답 단 전사본 20~40개 (Excel에서 라벨링).
- **정확도:** 필드별 — guidance 방향 정확도, themes precision/recall(통제 어휘라 깔끔히 측정), metrics 정확도.
- **캘리브레이션:** "confidence 0.9"가 실제로 ~90% 맞나? 깨지면 §6 자동승인이 무너짐.
- 산출 목표 문장 예: *"임계값 0.85에서 전사본 72% 자동 처리, guidance 정확도 96%, 검토 부담 28%, 비용 $N."*
## 8. 아키텍처 / 스택

> **무료 빌드 실측 (2026-06-20):** 아래 블록은 프로덕션/스케일 목표 아키텍처다. 실제 $0
> 포트폴리오 빌드의 결정 — 저장 = repo 내 로컬 JSON(`data/output/`, Supabase 대신) ·
> 스케줄 = 없음(on-demand, cron 제거) · 전사본 = 공개 출처 `.txt`(`data/transcripts/`,
> FMP 선택) · 추출 = **Claude Code 자체를 엔진으로**($0; `engine/extract.py`는 API 스케일
> 경로로 보존) · 대시보드 = 정적/후순위. 상세·실측 결과 = [CASE_STUDY.md](CASE_STUDY.md).

```
FMP (전사본, 라이브) ──[GitHub Actions cron, 어닝시즌 주기 실행]
   ↓
AI 표준화: Claude API + Pydantic (구조화 출력 = tool use, 타입 검증)
   · 대량 필드 추출 → Haiku 4.5 ($1/$5 per Mtok)
   · 애매/톤 판단만 → Sonnet 4.6 ($3/$15) 에스컬레이션
   ↓
confidence 분기 → 자동승인 / 리뷰 큐
   ↓
저장: Supabase
   ↓
대시보드: 뷰1 시스템 성능 / 뷰2 어닝 인텔리전스
   └ [별도] eval 하니스 → 성능 뷰에 숫자 공급
비용 레버: Batch API 50% 할인 + prompt caching(스키마·지시문 캐시 90% 절감)
```
## 9. 빌드 단계 (Build Phases)
- **Phase 0 ✅** — 전사본 더러움 확인, 스키마 v0 확정 (이 문서)
- **Phase 1** — 전사본 1개(테스트 케이스: NVDA Q1 FY2027)에서 표준 객체 추출 엔진
- **Phase 2** — confidence 생성 + 자동승인/검토 분기
- **Phase 3** — 골드셋 라벨링 + eval 하니스 + 임계값 튜닝  ← 포트폴리오 심장
- **Phase 4** — 워치리스트 10~20개로 확장, 배치 처리
- **Phase 5** — 대시보드 두 뷰
- **Phase 6** — 케이스 스터디 작성
> 원칙: 1개로 파이프라인 검증 → eval로 신뢰도 확보 → N개로 스케일.
> 결정마다 **"나중에 한 줄로 설명 가능한가?"** 를 기록 → 케이스 스터디 재료.
## 10. 가드레일
1. 투자 신호 도구가 아니라 **데이터 표준화·인텔리전스 도구**로 포지셔닝.
2. **PivoxQuant 재탕 아님** — 파이복스는 점수를 *매겼고*, 이건 앞단에서 지저분한 텍스트를 *표준화*한다.
## 11. 테스트 케이스 (Phase 1 입력)
- **NVDA Q1 FY2027** (발표 2026-05-20). 매출 $81,615M(+85% YoY, +20% QoQ),
  데이터센터 $75B, GM 74.9%, EPS $1.87(예상 $1.76 상회). 톤 명백히 confident.
  → 가이던스 방향·테마 추출·톤 분류를 검증하기 좋은 풍부한 샘플.
