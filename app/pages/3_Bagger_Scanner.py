"""Bagger Scanner — multi-bagger candidates (Mayer, O'Neil, Fisher, Lynch, Minervini)."""

from __future__ import annotations

import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))
from bootstrap import ensure_src_on_path

_src = ensure_src_on_path()
ROOT = _src.parent if _src.name == "src" else _src

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from astrotrading.auth_gate import logout_button, require_login
from astrotrading.bagger.engine import run_bagger_scanner
from astrotrading.bagger.literature import BIBLIOGRAPHY, PILLAR_META
from astrotrading.bagger.scoring import PILLAR_WEIGHTS
from astrotrading.bagger.universe import DEFAULT_BAGGER_UNIVERSE

st.set_page_config(page_title="Bagger Scanner · AstroTrading", page_icon="◈", layout="wide")
require_login()
logout_button()

st.title("Bagger Scanner")
st.caption(
    "Multi-bagger / 100-bagger candidates · Mayer · Phelps · O'Neil · Fisher · Lynch · Minervini"
)

with st.sidebar:
    st.header("Parámetros")
    top_n = st.slider("Top N", min_value=10, max_value=50, value=25)
    min_score = st.slider("Score mínimo", min_value=0, max_value=80, value=35, step=5)
    include_regime = st.checkbox("Filtro / aviso de régimen (Alfayate)", value=True)
    st.caption(f"Universo: {len(DEFAULT_BAGGER_UNIVERSE)} tickers líquidos US (ampliable).")
    run = st.button("Ejecutar scanner", type="primary", use_container_width=True)

    st.markdown("---")
    st.markdown("**Pesos de pilares**")
    for k, meta in PILLAR_META.items():
        st.caption(f"· {meta['label']}: {meta['weight']*100:.0f}%")


@st.cache_data(show_spinner="Escaneando universo (precios + fundamentals)…", ttl=1800)
def _scan(top_n: int, min_score: float, include_regime: bool) -> dict:
    result = run_bagger_scanner(
        top_n=top_n,
        min_score=float(min_score),
        include_regime=include_regime,
    )
    return result.to_dict()


if run or "bagger_result" not in st.session_state:
    try:
        st.session_state["bagger_result"] = _scan(top_n, min_score, include_regime)
        st.session_state["bagger_params"] = (top_n, min_score, include_regime)
    except Exception as exc:
        st.error(f"Error ejecutando Bagger Scanner: {exc}")
        st.stop()

# Re-run if params changed via controls after first load
params = (top_n, min_score, include_regime)
if st.session_state.get("bagger_params") != params and run:
    st.session_state["bagger_result"] = _scan(top_n, min_score, include_regime)
    st.session_state["bagger_params"] = params

data = st.session_state["bagger_result"]
regime = data.get("regime_label") or "Unknown"
color = {
    "Risk-On": "#3dd68c",
    "Favorable": "#3dd68c",
    "Neutral": "#f5c542",
    "Risk-Off": "#f07178",
    "Desfavorable": "#f07178",
    "Unknown": "#8b9cb3",
}.get(regime, "#8b9cb3")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Régimen (contexto)", regime)
m2.metric("Universo", data.get("universe_size", 0))
m3.metric("Escaneados", data.get("scanned", 0))
m4.metric("En ranking", len(data.get("candidates") or []))

st.markdown(
    f'<div style="padding:0.75rem 1rem;border-left:4px solid {color};'
    f'background:#121820;border-radius:0 8px 8px 0;margin:0.5rem 0 1.25rem 0;">'
    f"<strong style='color:{color}'>Contexto: {regime}</strong> · as of {data.get('as_of')} · "
    f"score min {min_score}"
    f"</div>",
    unsafe_allow_html=True,
)

if data.get("regime_warning"):
    st.warning(data["regime_warning"])

if data.get("regime_reasons"):
    with st.expander("Señales de régimen (Alfayate)", expanded=False):
        for r in data["regime_reasons"]:
            st.markdown(f"- {r}")

st.info(data.get("notes") or "")

# --- Filters on results ---
cands = list(data.get("candidates") or [])
if not cands:
    st.warning(
        "Sin candidatos con los filtros actuales. Baja el score mínimo o vuelve a ejecutar "
        "(yfinance puede fallar en algunos fundamentals)."
    )
else:
    sectors = sorted({c.get("sector") for c in cands if c.get("sector")})
    f1, f2, f3 = st.columns(3)
    with f1:
        sector_filter = st.multiselect("Filtrar sector", sectors, default=[])
    with f2:
        need_trend = st.checkbox("Solo > SMA200", value=False)
    with f3:
        need_quality = st.checkbox("Quality pilar ≥ 0.55", value=False)

    filtered = cands
    if sector_filter:
        filtered = [c for c in filtered if c.get("sector") in sector_filter]
    if need_trend:
        filtered = [
            c for c in filtered if (c.get("metrics") or {}).get("above_200dma") is True
        ]
    if need_quality:
        filtered = [
            c
            for c in filtered
            if (c.get("pillars") or {}).get("quality") is not None
            and c["pillars"]["quality"] >= 0.55
        ]

    st.subheader("Ranking de candidatos")
    rows = []
    for c in filtered:
        p = c.get("pillars") or {}
        m = c.get("metrics") or {}
        rows.append(
            {
                "#": c.get("rank"),
                "Ticker": c.get("symbol"),
                "Nombre": c.get("name") or "—",
                "Score": c.get("score"),
                "Quality": None if p.get("quality") is None else round(p["quality"], 2),
                "Growth": None if p.get("growth") is None else round(p["growth"], 2),
                "Momentum": None if p.get("momentum") is None else round(p["momentum"], 2),
                "Valuation": None if p.get("valuation") is None else round(p["valuation"], 2),
                "Bonus": None if p.get("bonus") is None else round(p["bonus"], 2),
                "Sector": c.get("sector") or "—",
                "RS 6m": (
                    None
                    if m.get("rs_6m") is None
                    else f"{m['rs_6m']*100:+.1f}%"
                ),
                "PEG": m.get("peg"),
                "Tags": ", ".join(c.get("literature_tags") or []) or "—",
            }
        )
    df = pd.DataFrame(rows)
    st.dataframe(df, hide_index=True, use_container_width=True)

    # Pillar radar for top 1
    if filtered:
        top = filtered[0]
        st.subheader(f"Perfil de pilares — #{top.get('rank')} {top.get('symbol')}")
        pillars = top.get("pillars") or {}
        labels = []
        values = []
        for key in ("quality", "growth", "momentum", "valuation", "bonus"):
            if pillars.get(key) is not None:
                labels.append(PILLAR_META[key]["label"].split("/")[0].strip()[:12])
                values.append(float(pillars[key]))
        if values:
            fig = go.Figure(
                data=go.Scatterpolar(
                    r=values + [values[0]],
                    theta=labels + [labels[0]],
                    fill="toself",
                    line=dict(color="#5b9fd4"),
                    fillcolor="rgba(91,159,212,0.25)",
                    name=top.get("symbol"),
                )
            )
            fig.update_layout(
                template="plotly_dark",
                height=320,
                margin=dict(l=40, r=40, t=30, b=30),
                paper_bgcolor="rgba(0,0,0,0)",
                polar=dict(
                    bgcolor="rgba(0,0,0,0)",
                    radialaxis=dict(visible=True, range=[0, 1]),
                ),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("Detalle y razones por candidato")
    for c in filtered[:20]:
        title = (
            f"#{c.get('rank')}  **{c.get('symbol')}**  · score **{c.get('score'):.1f}**"
            f"  · {c.get('name') or ''}"
        )
        with st.expander(title, expanded=c.get("rank") == 1):
            tags = c.get("literature_tags") or []
            if tags:
                st.markdown("**Etiquetas literarias:** " + " · ".join(f"`{t}`" for t in tags))
            p = c.get("pillars") or {}
            pc1, pc2, pc3, pc4, pc5 = st.columns(5)
            pc1.metric("Quality", "—" if p.get("quality") is None else f"{p['quality']:.2f}")
            pc2.metric("Growth", "—" if p.get("growth") is None else f"{p['growth']:.2f}")
            pc3.metric("Momentum", "—" if p.get("momentum") is None else f"{p['momentum']:.2f}")
            pc4.metric("Valuation", "—" if p.get("valuation") is None else f"{p['valuation']:.2f}")
            pc5.metric("Bonus", "—" if p.get("bonus") is None else f"{p['bonus']:.2f}")

            st.markdown("**Por qué entra en el ranking**")
            for reason in c.get("reasons") or []:
                st.markdown(f"- {reason}")

            m = c.get("metrics") or {}
            if m:
                st.markdown("**Métricas clave**")
                # pretty format growth-like fields
                show = {}
                for k, v in m.items():
                    if isinstance(v, float):
                        if k in (
                            "roe",
                            "roic",
                            "profit_margin",
                            "revenue_growth",
                            "earnings_growth",
                            "earnings_quarterly_growth",
                            "rs_3m",
                            "rs_6m",
                            "rs_12m",
                            "pct_from_52w_high",
                            "insider_pct",
                            "mom_3m",
                            "mom_6m",
                            "mom_12m",
                        ):
                            # values may already be fractions
                            show[k] = round(v, 4)
                        else:
                            show[k] = round(v, 4) if abs(v) < 1e6 else v
                    else:
                        show[k] = v
                st.json(show)

# --- Methodology ---
with st.expander("Metodología y bibliografía", expanded=False):
    st.markdown(
        """
### Score compuesto (0–100)

Cada pilar se normaliza a **[0, 1]**. Si faltan datos, se **renormalizan** los pesos
sobre los pilares disponibles (no se inventan métricas).
"""
    )
    wdf = pd.DataFrame(
        [
            {
                "Pilar": meta["label"],
                "Peso": f"{meta['weight']*100:.0f}%",
                "Métricas": ", ".join(meta["metrics"]),
                "Fuentes": meta["sources"][0],
            }
            for meta in PILLAR_META.values()
        ]
    )
    st.dataframe(wdf, hide_index=True, use_container_width=True)

    st.markdown("### Bibliografía de referencia")
    for b in BIBLIOGRAPHY:
        st.markdown(f"- **{b['author']}** — *{b['work']}*: {b['role']}")

    st.markdown(
        """
### Limitaciones (honestas)

- yfinance no siempre expone ROIC, PEG o insider ownership fiables.
- Un high score **no** garantiza un multi-bagger (Mayer/Phelps insisten en tiempo y rareza).
- El régimen de mercado (O'Neil) es un filtro de contexto, no un veto duro.
- Herramienta privada de investigación — no es consejo de inversión.
"""
    )

st.markdown("---")
st.caption(
    "Bagger Scanner · pesos: Quality 30% · Growth 25% · Momentum 25% · Valuation 15% · Bonus 5%. "
    "No es consejo de inversión."
)
