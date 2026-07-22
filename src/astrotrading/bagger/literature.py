"""
Bibliographic mapping for the Bagger Scanner.

Each scoring pillar cites the primary authors so the ranking remains
transparent and non-arbitrary. Weights are research heuristics for a private
MVP — not a claim of predicting 100-baggers.
"""

from __future__ import annotations

# Pillar → (default weight, short label, sources)
PILLAR_META: dict[str, dict] = {
    "quality": {
        "weight": 0.30,
        "label": "Capital Efficiency / Quality",
        "sources": [
            "Christopher Mayer — 100 Baggers (ROIC/ROE, durable economics)",
            "Philip Fisher — Common Stocks and Uncommon Profits (quality franchise)",
            "Thomas Phelps — 100 to 1 (companies that compound capital well)",
        ],
        "metrics": ["ROE", "profit margin", "debt/equity (penalty)"],
    },
    "growth": {
        "weight": 0.25,
        "label": "Growth",
        "sources": [
            "Mayer — 100 Baggers (sales & earnings growth as compounding fuel)",
            "William O'Neil — CAN SLIM (A = Annual earnings, C = Current earnings)",
            "Peter Lynch — One Up on Wall Street (growth that can become a ten-bagger)",
        ],
        "metrics": ["revenue growth", "earnings growth", "earnings acceleration proxy"],
    },
    "momentum": {
        "weight": 0.25,
        "label": "Momentum / Relative Strength",
        "sources": [
            "O'Neil — CAN SLIM (R = Relative Strength leaders)",
            "Mark Minervini — Trade Like a Stock Market Wizard (Trend Template / SEPA)",
            "Lynch — momentum confirms institutional sponsorship of winners",
        ],
        "metrics": ["RS 3m/6m/12m vs SPX", "distance to 52w high", "SMA50/SMA200"],
    },
    "valuation": {
        "weight": 0.15,
        "label": "Valuation Reasonableness",
        "sources": [
            "Lynch — PEG and growth-at-a-reasonable-price",
            "Mayer — avoid paying any price; valuation still matters at the margin",
            "Phelps — patience works better when entry is not extreme",
        ],
        "metrics": ["PEG", "trailing P/E vs growth context"],
    },
    "bonus": {
        "weight": 0.05,
        "label": "Qualitative Bonus",
        "sources": [
            "Fisher / Mayer — skin in the game (insider / owner-operator)",
            "Mayer — capital return (buybacks) can boost per-share compounding",
        ],
        "metrics": ["insider ownership", "buyback yield / share reduction proxy"],
    },
}

BIBLIOGRAPHY = [
    {
        "author": "Christopher Mayer",
        "work": "100 Baggers",
        "role": "Primary multi-bagger framework: quality, growth, long holding, economics",
    },
    {
        "author": "Thomas Phelps",
        "work": "100 to 1 in the Stock Market",
        "role": "Historical 100-bagger characteristics and patience",
    },
    {
        "author": "William O'Neil",
        "work": "How to Make Money in Stocks (CAN SLIM)",
        "role": "Earnings growth + relative strength + market direction",
    },
    {
        "author": "Philip Fisher",
        "work": "Common Stocks and Uncommon Profits",
        "role": "Franchise quality, management, scuttlebutt principles",
    },
    {
        "author": "Peter Lynch",
        "work": "One Up on Wall Street",
        "role": "Ten-baggers, PEG, growth at reasonable price",
    },
    {
        "author": "Mark Minervini",
        "work": "Trade Like a Stock Market Wizard (SEPA / Trend Template)",
        "role": "Price structure: SMA stack, 52w highs, RS leadership",
    },
]
