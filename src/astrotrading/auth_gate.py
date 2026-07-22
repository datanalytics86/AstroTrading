"""
Simple single-user authentication for Streamlit.

Uses ASTROTRADING_USERNAME / ASTROTRADING_PASSWORD from environment or
.streamlit/secrets.toml. Password may be plaintext (MVP) or bcrypt hash
(prefix: bcrypt$).
"""

from __future__ import annotations

import hmac
import os
from typing import Callable

import streamlit as st


def _get_secret(key: str, default: str = "") -> str:
    # Env first
    val = os.getenv(key, "").strip()
    if val:
        return val
    try:
        return str(st.secrets.get(key, default) or default).strip()
    except Exception:
        return default


def _verify_password(plain: str, expected: str) -> bool:
    if not expected:
        return False
    if expected.startswith("bcrypt$") or expected.startswith("$2"):
        try:
            import bcrypt

            token = expected.replace("bcrypt$", "", 1) if expected.startswith("bcrypt$") else expected
            return bcrypt.checkpw(plain.encode("utf-8"), token.encode("utf-8"))
        except Exception:
            return False
    # Constant-time compare for plaintext MVP secret
    return hmac.compare_digest(plain.encode("utf-8"), expected.encode("utf-8"))


def require_login(
    title: str = "AstroTrading — Acceso privado",
) -> bool:
    """
    Render login form if not authenticated. Returns True when session is authorized.
    """
    if st.session_state.get("authenticated") is True:
        return True

    username_expected = _get_secret("ASTROTRADING_USERNAME", "owner")
    password_expected = _get_secret("ASTROTRADING_PASSWORD", "")

    # Fail closed if no password configured
    st.markdown(
        """
        <style>
        .login-box { max-width: 420px; margin: 4rem auto; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title(title)
    st.caption("Dashboard privado · un solo usuario autorizado")

    if not password_expected:
        st.error(
            "Auth no configurada. Define `ASTROTRADING_PASSWORD` en `.env` o "
            "`.streamlit/secrets.toml` (ver `.env.example`)."
        )
        st.stop()
        return False

    with st.form("login_form", clear_on_submit=False):
        user = st.text_input("Usuario", value="", autocomplete="username")
        pwd = st.text_input("Contraseña", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Entrar", use_container_width=True)

    if submitted:
        user_ok = hmac.compare_digest(user.strip().encode("utf-8"), username_expected.encode("utf-8"))
        pwd_ok = _verify_password(pwd, password_expected)
        if user_ok and pwd_ok:
            st.session_state["authenticated"] = True
            st.session_state["auth_user"] = user.strip()
            st.rerun()
        else:
            st.error("Credenciales incorrectas.")

    st.stop()
    return False


def logout_button() -> None:
    if st.sidebar.button("Cerrar sesión", use_container_width=True):
        st.session_state["authenticated"] = False
        st.session_state.pop("auth_user", None)
        st.rerun()
