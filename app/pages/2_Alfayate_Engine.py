"""Alfayate Engine — top-down regime + relative strength ranking."""

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
import streamlit as st

from astrotrading.agents.narratives import generate_alfayate_narrative
from astrotrading.alfayate.engine import DEFAULT_UNIVERSE, run_alfayate_engine
from astrotrading.auth_gate import logout_button, require_login

st.set_page_config(page_title="Alfayate Engine · AstroTrading", page_icon="◈", layout="wide")
require_login()
logout_button()

st.title("Alfayate Engine")
st.caption("Top-down: régimen macro / intermarket → ranking de relative strength")

with st.sidebar:
    st.header("Parámetros")
    top_n = st.slider("Top N acciones", min_value=5, max_value=25, value=15)
    st.caption(f"Universo MVP: {len(DEFAULT_UNIVERSE)} tickers líquidos US.")
    run = st.button("Ejecutar motor", type="primary", use_container_width=True)


@st.cache_data(show_spinner="Ejecutando Alfayate Engine (descarga de mercado)…", ttl=1800)
def _run(top_n: int) -> dict:
    result = run_alfayate_engine(top_n=top_n)
    return result.to_dict()


if run or "alfayate_result" not in st.session_state:
    try:
        st.session_state["alfayate_result"] = _run(top_n)
    except Exception as exc:
        st.error(f"Error ejecutando motor: {exc}")
        st.stop()

data = st.session_state["alfayate_result"]
label = data["macro_label"]
color = {"Risk-On": "#3dd68c", "Neutral": "#f5c542", "Risk-Off": "#f07178"}.get(label, "#8b9cb3")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Régimen macro", label)
m2.metric("Score macro", f"{data['macro_score']:+.2f}")
b50 = data.get("breadth_above_50")
b200 = data.get("breadth_above_200")
m3.metric("% > SMA50", f"{b50*100:.0f}%" if b50 is not None else "—")
m4.metric("% > SMA200", f"{b200*100:.0f}%" if b200 is not None else "—")

st.markdown(
    f'<div style="padding:0.75rem 1rem;border-left:4px solid {color};'
    f'background:#121820;border-radius:0 8px 8px 0;margin:0.5rem 0 1.25rem 0;">'
    f"<strong style='color:{color}'>{label}</strong> · as of {data['as_of']} · "
    f"universo {data['universe_size']} tickers"
    f"</div>",
    unsafe_allow_html=True,
)

# Step 1 — macro
st.subheader("1. Régimen de fondo (intermarket + tendencia)")
for reason in data.get("macro_reasons") or []:
    st.markdown(f"- {reason}")
st.info(data.get("notes") or "")

with st.expander("Narrativa del agente", expanded=True):
    if st.button("Generar narrativa Alfayate (LLM o plantilla)"):
        with st.spinner("Generando…"):
            st.session_state["alfayate_narrative"] = generate_alfayate_narrative(data)
    st.markdown(st.session_state.get("alfayate_narrative") or "_Pulsa el botón para generar la narrativa._")

# Step 2 — ranking
st.subheader("2. Ranking de acciones ganadoras (RS / momentum)")
cands = data.get("candidates") or []
if not cands:
    st.warning("Sin candidatos — revisa conectividad yfinance o reduce el universo.")
else:
    rows = []
    for c in cands:
        rows.append(
            {
                "#": c["rank"],
                "Ticker": c["symbol"],
                "Score": c["score"],
                "RS 3m": f"{c['rs_3m']*100:+.1f}%",
                "RS 6m": f"{c['rs_6m']*100:+.1f}%",
                "RS 12m": f"{c['rs_12m']*100:+.1f}%",
                "Mom 6m": f"{c['mom_6m']*100:+.1f}%",
                ">50d": "✓" if c["above_50dma"] else "·",
                ">200d": "✓" if c["above_200dma"] else "·",
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    st.markdown("##### Razones por candidato")
    for c in cands[:10]:
        with st.expander(f"#{c['rank']}  {c['symbol']}  · score {c['score']:+.3f}"):
            for r in c.get("reasons") or []:
                st.markdown(f"- {r}")

st.markdown("---")
st.caption(
    "Proceso Alfayate-style MVP: (1) régimen con SPX trend, SPX/Gold, HYG/TLT, BTC; "
    "(2) ranking RS 3/6/12m vs SPX + filtros SMA. No es consejo de inversión."
)
