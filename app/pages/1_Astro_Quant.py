"""Astro Quant dashboard — Cyclic Index + multi-asset comparison + regime."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from astrotrading.agents.narratives import generate_regime_narrative
from astrotrading.auth_gate import logout_button, require_login
from astrotrading.data_service import (
    asset_labels,
    build_comparison,
    build_regime,
    current_index,
    load_market_panel,
    load_or_build_cyclic_series,
)

st.set_page_config(page_title="Astro Quant · AstroTrading", page_icon="◈", layout="wide")
require_login()
logout_button()

st.title("Astro Quant")
st.caption("Cyclic Index de André Barbault · multi-asset · señal de régimen")

# --- Controls ---
with st.sidebar:
    st.header("Parámetros")
    frame = st.selectbox("Frame", ["heliocentric", "geocentric"], index=0)
    start = st.selectbox("Inicio histórico", ["2000-01-01", "1990-01-01", "2010-01-01"], index=0)
    step = st.selectbox("Muestreo (días)", [7, 14, 30], index=0)
    rebuild = st.checkbox("Forzar recálculo del índice", value=False)
    run = st.button("Actualizar datos", type="primary", use_container_width=True)

@st.cache_data(show_spinner="Calculando Cyclic Index histórico…", ttl=3600)
def _cached_cyclic(start: str, step: int, frame: str, rebuild: bool) -> pd.DataFrame:
    return load_or_build_cyclic_series(start=start, step_days=step, frame=frame, force_rebuild=rebuild)


@st.cache_data(show_spinner="Descargando mercados…", ttl=3600)
def _cached_market(start: str) -> pd.DataFrame:
    return load_market_panel(start=start)


# Auto-load on first visit
if "aq_loaded" not in st.session_state or run:
    st.session_state["aq_loaded"] = True

with st.spinner("Cargando motor Astro Quant…"):
    cyclic_df = _cached_cyclic(start, step, frame, rebuild)
    market = _cached_market(start)
    today_res = current_index(frame=frame)
    regime = build_regime(cyclic_df, step_days=step)
    comparison = build_comparison(cyclic_df, market) if not market.empty else None
    labels = asset_labels()

# --- KPI row ---
regime_color = {
    "Favorable": "#3dd68c",
    "Neutral": "#f5c542",
    "Desfavorable": "#f07178",
}.get(regime.label, "#8b9cb3")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Cyclic Index (hoy)", f"{today_res.index:.2f}°")
k2.metric("Régimen", regime.label)
k3.metric("Percentil histórico", f"{regime.percentile:.0f}%")
k4.metric("Z-score", f"{regime.zscore:+.2f}")
k5.metric("Pendiente 1y", f"{regime.slope_1y:+.1f}°/a")

st.markdown(
    f'<div style="padding:0.75rem 1rem;border-left:4px solid {regime_color};'
    f'background:#121820;border-radius:0 8px 8px 0;margin:0.5rem 0 1.25rem 0;">'
    f'<strong style="color:{regime_color}">Señal: {regime.label}</strong> · score {regime.score:+.2f} · frame {frame} · as of {regime.as_of}'
    f"</div>",
    unsafe_allow_html=True,
)

# --- Narrative ---
with st.expander("Narrativa / justificación del régimen", expanded=True):
    if st.button("Generar narrativa (LLM o plantilla)"):
        with st.spinner("Generando…"):
            st.session_state["regime_narrative"] = generate_regime_narrative(regime.to_dict())
    narrative = st.session_state.get("regime_narrative") or regime.justification
    st.markdown(narrative)

# --- Historical chart ---
st.subheader("Histórico del Cyclic Index")
fig_ci = go.Figure()
fig_ci.add_trace(
    go.Scatter(
        x=cyclic_df["date"],
        y=cyclic_df["cyclic_index"],
        mode="lines",
        name="Cyclic Index",
        line=dict(color="#5b9fd4", width=2),
        fill="tozeroy",
        fillcolor="rgba(91,159,212,0.08)",
    )
)
# percentile bands
mu = cyclic_df["cyclic_index"].mean()
p25 = cyclic_df["cyclic_index"].quantile(0.25)
p75 = cyclic_df["cyclic_index"].quantile(0.75)
fig_ci.add_hline(y=mu, line_dash="dot", line_color="#8b9cb3", annotation_text="media")
fig_ci.add_hrect(y0=p25, y1=p75, fillcolor="rgba(245,197,66,0.06)", line_width=0)
fig_ci.update_layout(
    template="plotly_dark",
    height=420,
    margin=dict(l=20, r=20, t=30, b=20),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    yaxis_title="Índice (°)",
    xaxis_title=None,
    showlegend=False,
)
st.plotly_chart(fig_ci, use_container_width=True)

# Pair breakdown for today
with st.expander("Detalle del cálculo (hoy)"):
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Longitudes eclípticas**")
        lon_df = pd.DataFrame(
            [{"Planeta": k.title(), "Longitud (°)": f"{v:.4f}"} for k, v in today_res.longitudes.items()]
        )
        st.dataframe(lon_df, hide_index=True, use_container_width=True)
    with c2:
        st.markdown("**10 distancias angulares mínimas**")
        pair_df = pd.DataFrame(
            [{"Par": k, "Arco (°)": round(v, 4)} for k, v in sorted(today_res.pairs.items())]
        )
        st.dataframe(pair_df, hide_index=True, use_container_width=True)
        st.caption(f"Suma = **{today_res.index:.4f}°** = Cyclic Index")

# --- Multi-asset comparison ---
st.subheader("Comparativa multi-asset (rebase 100)")
if comparison is None or comparison["panel_rebased"].empty:
    st.warning("No hay datos de mercado disponibles (yfinance). Reintenta más tarde.")
else:
    rebased = comparison["panel_rebased"].copy()
    # Normalize cyclic index onto secondary axis-friendly scale for overlay option
    asset_cols = [c for c in rebased.columns if c != "cyclic_index"]

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    colors = {
        "spx": "#e6edf3",
        "gold": "#f5c542",
        "btc": "#f7931a",
        "wti": "#e85d4c",
        "copper": "#cd7f32",
    }
    for col in asset_cols:
        fig.add_trace(
            go.Scatter(
                x=rebased.index,
                y=rebased[col],
                name=labels.get(col, col),
                line=dict(color=colors.get(col, "#8b9cb3"), width=1.5),
            ),
            secondary_y=False,
        )
    # CI on secondary axis (raw level)
    fig.add_trace(
        go.Scatter(
            x=rebased.index,
            y=rebased["cyclic_index"],
            name="Cyclic Index",
            line=dict(color="#5b9fd4", width=2, dash="dash"),
        ),
        secondary_y=True,
    )
    fig.update_layout(
        template="plotly_dark",
        height=480,
        margin=dict(l=20, r=20, t=30, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    fig.update_yaxes(title_text="Precio rebased (100)", secondary_y=False)
    fig.update_yaxes(title_text="Cyclic Index (°)", secondary_y=True)
    st.plotly_chart(fig, use_container_width=True)

    # Regression table
    st.markdown("##### Regresión simple: retorno forward ~63d ~ α + β · Cyclic Index")
    regs = comparison["regressions"]
    reg_df = pd.DataFrame(
        [
            {
                "Activo": labels.get(r.asset, r.asset),
                "β": r.beta,
                "α": r.alpha,
                "R²": r.r_squared,
                "corr(CI, fwd ret)": r.corr,
                "corr(ΔCI, ret)": r.correlation_with_delta_ci,
                "n": r.n_obs,
            }
            for r in regs
        ]
    )
    st.dataframe(reg_df, hide_index=True, use_container_width=True)
    st.caption(
        "β < 0 sugiere que niveles altos del índice se asocian a retornos forward más bajos "
        "(relación estadística descriptiva, no causalidad)."
    )

    # Correlation heatmap-ish table
    c_delta = comparison["correlations_delta"]
    st.markdown("##### Correlación ΔCI vs retornos diarios del activo")
    corr_df = pd.DataFrame(
        [{"Activo": labels.get(k, k), "corr(ΔCI, r)": round(v, 4) if v == v else None} for k, v in c_delta.items()]
    )
    st.dataframe(corr_df, hide_index=True, use_container_width=True)

# Context box
with st.expander("Contexto histórico del régimen"):
    st.json(regime.context)

st.markdown("---")
st.caption(
    "Fórmula: suma de las 10 distancias angulares mínimas (≤180°) entre Júpiter, Saturno, "
    "Urano, Neptuno y Plutón. Efemérides JPL DE421 vía skyfield. No es consejo de inversión."
)
