"""
Narrative layer — LLM agents with deterministic template fallback.

Priority:
  1. xAI Grok (XAI_API_KEY)
  2. OpenAI-compatible (OPENAI_API_KEY)
  3. Local template narrative (always available, no network)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def _llm_chat(system: str, user: str) -> str | None:
    """Call xAI or OpenAI-compatible chat API. Returns None on failure."""
    xai_key = os.getenv("XAI_API_KEY", "").strip()
    oai_key = os.getenv("OPENAI_API_KEY", "").strip()

    if xai_key:
        base = "https://api.x.ai/v1"
        key = xai_key
        model = os.getenv("XAI_MODEL", "grok-2-latest")
    elif oai_key:
        base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        key = oai_key
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    else:
        return None

    try:
        import httpx

        resp = httpx.post(
            f"{base}/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "temperature": 0.4,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=45.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logger.warning("LLM narrative failed: %s", exc)
        return None


def _template_regime(payload: dict[str, Any]) -> str:
    label = payload.get("label", "Neutral")
    idx = payload.get("current_index", 0)
    pct = payload.get("percentile", 50)
    z = payload.get("zscore", 0)
    s1 = payload.get("slope_1y", 0)
    ctx = payload.get("context") or {}

    tone = {
        "Favorable": "sesgo constructivo",
        "Neutral": "equilibrio sin sesgo claro",
        "Desfavorable": "sesgo de cautela",
    }.get(label, "equilibrio")

    return (
        f"**Lectura Astro Quant ({label})** — {tone}.\n\n"
        f"El Cyclic Index de Barbault cotiza en **{idx:.1f}°**, percentil **{pct:.0f}%** "
        f"del histórico de referencia (z-score {z:+.2f}). "
        f"La pendiente a 1 año es **{s1:+.1f}°/año**. "
        f"Rango histórico observado: {ctx.get('hist_min', '—')}° "
        f"({ctx.get('hist_min_date', '')}) → {ctx.get('hist_max', '—')}° "
        f"({ctx.get('hist_max_date', '')}).\n\n"
        f"{payload.get('justification', '')}\n\n"
        "_Interpretación de investigación: un índice más bajo implica menor dispersión angular "
        "entre planetas lentos (Júpiter–Plutón); un índice alto, mayor dispersión. "
        "No constituye recomendación de inversión._"
    )


def _template_alfayate(payload: dict[str, Any]) -> str:
    label = payload.get("macro_label", "Neutral")
    score = payload.get("macro_score", 0)
    reasons = payload.get("macro_reasons") or []
    cands = payload.get("candidates") or []
    top = ", ".join(c.get("symbol", "") for c in cands[:5]) or "—"
    breadth = ""
    if payload.get("breadth_above_200") is not None:
        breadth = (
            f" Amplitud: {payload['breadth_above_50']*100:.0f}% del universo > SMA50; "
            f"{payload['breadth_above_200']*100:.0f}% > SMA200."
        )

    bullets = "\n".join(f"- {r}" for r in reasons[:5])
    return (
        f"**Alfayate Engine — régimen {label}** (score {score:+.2f}).{breadth}\n\n"
        f"**Señales top-down:**\n{bullets}\n\n"
        f"**Líderes RS (top):** {top}.\n\n"
        f"{payload.get('notes', '')}\n\n"
        "_Proceso: primero el régimen macro/intermarket; después el ranking de relative strength. "
        "Herramienta privada de investigación._"
    )


def generate_regime_narrative(regime_dict: dict[str, Any]) -> str:
    """Narrative for Astro Quant regime panel."""
    system = (
        "Eres un analista quant senior de un family office. Explicas el Cyclic Index de "
        "André Barbault y su régimen (Favorable/Neutral/Desfavorable) con rigor, sin "
        "sensacionalismo y sin dar consejos de inversión personalizados. Responde en "
        "español, 2-3 párrafos, markdown ligero."
    )
    user = (
        "Genera la narrativa del dashboard a partir de este JSON de régimen:\n"
        + json.dumps(regime_dict, ensure_ascii=False, indent=2)
    )
    text = _llm_chat(system, user)
    return text or _template_regime(regime_dict)


def generate_alfayate_narrative(result_dict: dict[str, Any]) -> str:
    """Narrative for Alfayate module."""
    system = (
        "Eres un estratega de mercados estilo top-down (intermarket + amplitud + relative strength), "
        "inspirado en el marco de Javier Alfayate. Explicas régimen y ranking de acciones líderes "
        "con claridad institucional. Español, 2-3 párrafos, sin consejos personalizados."
    )
    # keep prompt small
    slim = {
        "macro_label": result_dict.get("macro_label"),
        "macro_score": result_dict.get("macro_score"),
        "macro_reasons": result_dict.get("macro_reasons"),
        "breadth_above_50": result_dict.get("breadth_above_50"),
        "breadth_above_200": result_dict.get("breadth_above_200"),
        "notes": result_dict.get("notes"),
        "candidates": (result_dict.get("candidates") or [])[:8],
    }
    user = "Genera la narrativa del módulo Alfayate:\n" + json.dumps(slim, ensure_ascii=False, indent=2)
    text = _llm_chat(system, user)
    return text or _template_alfayate(result_dict)
