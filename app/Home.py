"""
AstroTrading — private Streamlit entrypoint.

Run:
  streamlit run app/Home.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import streamlit as st

from astrotrading.auth_gate import logout_button, require_login

st.set_page_config(
    page_title="AstroTrading",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Dark fintech theme polish
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
    html, body, [class*="css"]  {
        font-family: 'IBM Plex Sans', sans-serif;
    }
    .block-container { padding-top: 1.5rem; }
    div[data-testid="stMetricValue"] {
        font-family: 'IBM Plex Mono', monospace;
    }
    .hero-title {
        font-size: 1.75rem; font-weight: 600; letter-spacing: -0.02em;
        margin-bottom: 0.25rem;
    }
    .hero-sub { color: #8b9cb3; margin-bottom: 1.5rem; }
    .card {
        background: linear-gradient(145deg, #121820 0%, #0d1218 100%);
        border: 1px solid #1e2a3a;
        border-radius: 12px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

require_login()
logout_button()

st.sidebar.markdown("### AstroTrading")
st.sidebar.caption(f"Usuario: `{st.session_state.get('auth_user', '—')}`")
st.sidebar.markdown("---")
st.sidebar.markdown(
    """
**Módulos**
- ◎ **Astro Quant** — Cyclic Index + multi-asset
- ◎ **Alfayate Engine** — top-down + RS
"""
)

st.markdown('<div class="hero-title">AstroTrading</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-sub">Dashboard privado · Cyclic Index de Barbault + motor top-down Alfayate</div>',
    unsafe_allow_html=True,
)

col1, col2 = st.columns(2)
with col1:
    st.markdown("#### Astro Quant")
    st.write(
        "Cálculo **determinístico** del Cyclic Index (Júpiter–Plutón), "
        "serie histórica, señal de régimen y comparativa vs S&P 500, Oro, Bitcoin, WTI y Cobre."
    )
    st.page_link("pages/1_Astro_Quant.py", label="Abrir Astro Quant →", icon="📈")

with col2:
    st.markdown("#### Alfayate Engine")
    st.write(
        "Análisis top-down: primero régimen macro/intermarket/amplitud, "
        "después ranking de acciones líderes por relative strength y momentum."
    )
    st.page_link("pages/2_Alfayate_Engine.py", label="Abrir Alfayate Engine →", icon="🧭")

st.markdown("---")
st.markdown("#### Stack del MVP")
st.code(
    "Python · Streamlit · skyfield/JPL DE421 · yfinance · Plotly · agents LLM (xAI/OpenAI opcional)",
    language="text",
)
st.info(
    "Usa el menú lateral de Streamlit para navegar entre páginas. "
    "La primera carga del índice histórico descarga el kernel JPL (~17MB) y puede tardar unos minutos."
)
