"""
Configurable liquid universe for the Bagger Scanner.

~200 US tickers: S&P-style large caps + quality growth / mid-caps often
associated with multi-bagger searches (liquid enough for yfinance MVP).

Expand by appending tickers to EXTRA_TICKERS or replacing DEFAULT_BAGGER_UNIVERSE.
"""

from __future__ import annotations

# Core large-cap / liquid names
_CORE: tuple[str, ...] = (
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "TSLA", "BRK-B", "JPM",
    "V", "UNH", "XOM", "LLY", "MA", "COST", "HD", "PG", "JNJ", "ABBV",
    "CRM", "ORCL", "BAC", "WMT", "CVX", "MRK", "KO", "PEP", "AMD", "NFLX",
    "ADBE", "CSCO", "ACN", "TMO", "MCD", "INTC", "IBM", "CAT", "GE", "GS",
    "AXP", "MS", "BA", "DIS", "PFE", "PM", "NEE", "TXN", "QCOM", "INTU",
    "AMAT", "ISRG", "BKNG", "NOW", "UBER", "SPGI", "BLK", "SYK", "DE", "LOW",
    "LRCX", "TJX", "GILD", "MDT", "ADI", "VRTX", "PANW", "SBUX", "PLD", "CB",
    "MMC", "SO", "CI", "BMY", "MO", "DUK", "EQIX", "SHW", "ZTS", "CME",
    "PH", "BSX", "KLAC", "SNPS", "CDNS", "ANET", "APH", "TDG", "TT", "CMG",
)

# Growth / quality mid & large often in multi-bagger screens
_GROWTH_QUALITY: tuple[str, ...] = (
    "CRWD", "DDOG", "SNOW", "NET", "ZS", "OKTA", "TEAM", "SHOP", "SQ", "COIN",
    "MELI", "SE", "NU", "PATH", "PLTR", "AI", "SMCI", "ARM", "APP", "MNDY",
    "TTD", "ROKU", "PINS", "SNAP", "DASH", "ABNB", "RBLX", "U", "HUBS", "WDAY",
    "VEEV", "FTNT", "DDOG", "MDB", "ESTC", "BILL", "TOST", "DUOL", "CELH", "DECK",
    "LULU", "NKE", "ONON", "BIRK", "POOL", "ODFL", "URI", "PCAR", "CTAS", "FAST",
    "CPR", "FIX", "AXON", "VRT", "PWR", "ETN", "HUBB", "CARR", "JCI", "IR",
    "ENPH", "FSLR", "RUN", "SEDG", "BE", "PLUG", "CCJ", "VST", "CEG", "NRG",
    "TSM", "ASML", "MU", "MRVL", "ON", "NXPI", "MPWR", "TER", "ENTG", "WOLF",
    "REGN", "ALNY", "ARGX", "INCY", "BIIB", "AMGN", "DXCM", "PODD", "IDXX", "IQV",
    "ELV", "HCA", "CNC", "HUM", "CI", "MOH", "UNH", "TMO", "DHR", "A",
    "MSCI", "MCO", "FICO", "ICE", "CME", "NDAQ", "SCHW", "IBKR", "TROW", "BEN",
    "COST", "WMT", "TGT", "DG", "DLTR", "ROST", "BURL", "ULTA", "DPZ", "YUM",
    "MAR", "HLT", "RCL", "CCL", "NCLH", "BKNG", "EXPE", "ABNB", "DAL", "UAL",
    "LMT", "RTX", "NOC", "GD", "HII", "LHX", "TDG", "HEI", "AXON", "KTOS",
    "FCX", "NEM", "SCCO", "AA", "X", "CLF", "NUE", "STLD", "RS", "MLI",
    "LIN", "APD", "ECL", "SHW", "PPG", "DD", "DOW", "LYB", "CF", "MOS",
    "COP", "EOG", "PXD", "MPC", "VLO", "PSX", "OXY", "HES", "DVN", "FANG",
    "AMT", "CCI", "SBAC", "DLR", "EQIX", "PSA", "O", "SPG", "WELL", "VICI",
)

# Extra mid-caps / compounders
_EXTRA: tuple[str, ...] = (
    "CPRT", "ROL", "WSO", "GWW", "AME", "ROP", "ITW", "EMR", "ROK", "DOV",
    "XYL", "IEX", "FTV", "KEYS", "TRMB", "ZBRA", "TDY", "GNRC", "AYI", "LECO",
    "TREX", "BLDR", "MAS", "OC", "AZEK", "SITE", "WMS", "UFPI", "SSD", "FBIN",
    "TWLO", "ZM", "DOCU", "DBX", "BOX", "PCTY", "PAYC", "CFLT", "GTLB", "S",
    "HOOD", "SOFI", "AFRM", "UPST", "LC", "OWL", "KKR", "BX", "APO", "CG",
    "TPL", "FICO", "IT", "EFX", "VRSK", "CTSH", "EPAM", "GLOB", "INFY", "WIT",
)


def _dedupe(*groups: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for group in groups:
        for t in group:
            u = t.upper().strip()
            if u and u not in seen:
                seen.add(u)
                out.append(u)
    return tuple(out)


DEFAULT_BAGGER_UNIVERSE: tuple[str, ...] = _dedupe(_CORE, _GROWTH_QUALITY, _EXTRA)

# Alias for external expansion
EXTRA_TICKERS: tuple[str, ...] = ()


def resolve_universe(extra: list[str] | None = None) -> list[str]:
    """Return full universe list, optionally extended."""
    base = list(DEFAULT_BAGGER_UNIVERSE)
    if EXTRA_TICKERS:
        base = list(_dedupe(tuple(base), EXTRA_TICKERS))
    if extra:
        base = list(_dedupe(tuple(base), tuple(extra)))
    return base
