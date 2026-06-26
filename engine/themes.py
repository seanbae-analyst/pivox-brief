"""Theme taxonomy for the personalized brief — the 'pick what you want to see' universe.

Each theme groups buzzy US + KR tickers. The user subscribes to themes (engine/watchlist.py);
the brief's 🔥 hot-movers are then drawn from the union of their chosen themes (+ any custom
tickers), ranked by today's move. KR symbols carry a .KS (KOSPI) / .KQ (KOSDAQ) suffix, which
is also how the renderer splits 🇺🇸 vs 🇰🇷. All tickers verified resolvable via yfinance.
"""
from __future__ import annotations

THEMES: dict[str, dict] = {
    "ai_semi": {
        "label": "AI·반도체",
        "tickers": [("엔비디아", "NVDA"), ("브로드컴", "AVGO"), ("AMD", "AMD"),
                    ("슈마이", "SMCI"), ("ASML", "ASML"),
                    ("삼성전자", "005930.KS"), ("SK하이닉스", "000660.KS"), ("한미반도체", "042700.KS")],
    },
    "battery_ev": {
        "label": "2차전지·전기차",
        "tickers": [("테슬라", "TSLA"), ("리비안", "RIVN"),
                    ("LG엔솔", "373220.KS"), ("삼성SDI", "006400.KS"),
                    ("에코프로", "086520.KQ"), ("에코프로비엠", "247540.KQ")],
    },
    "bio": {
        "label": "바이오·제약",
        "tickers": [("일라이릴리", "LLY"), ("노보", "NVO"),
                    ("삼성바이오", "207940.KS"), ("알테오젠", "196170.KQ"), ("셀트리온", "068270.KS")],
    },
    "defense": {
        "label": "방산",
        "tickers": [("록히드", "LMT"), ("RTX", "RTX"),
                    ("한화에어로", "012450.KS"), ("LIG넥스원", "079550.KS"), ("한국항공우주", "047810.KS")],
    },
    "nuclear_power": {
        "label": "원전·전력",
        "tickers": [("컨스텔레이션", "CEG"), ("뉴스케일", "SMR"),
                    ("두산에너빌리티", "034020.KS"), ("한전KPS", "051600.KS")],
    },
    "crypto_fintech": {
        "label": "코인·핀테크",
        "tickers": [("코인베이스", "COIN"), ("마스트", "MSTR"), ("로빈후드", "HOOD")],
    },
    "bigtech": {
        "label": "빅테크",
        "tickers": [("애플", "AAPL"), ("마이크로소프트", "MSFT"), ("메타", "META"),
                    ("아마존", "AMZN"), ("알파벳", "GOOGL"), ("넷플릭스", "NFLX")],
    },
    "platform_kr": {
        "label": "한국 플랫폼·내수",
        "tickers": [("카카오", "035720.KS"), ("네이버", "035420.KS"),
                    ("현대차", "005380.KS"), ("포스코홀딩스", "005490.KS")],
    },
}


def theme_labels() -> dict[str, str]:
    return {k: v["label"] for k, v in THEMES.items()}
