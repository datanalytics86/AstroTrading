"""
Simple single-user authentication for Streamlit.

Uses ASTROTRADING_USERNAME / ASTROTRADING_PASSWORD from environment or
.streamlit/secrets.toml. Password may be plaintext (MVP) or bcrypt hash
(prefix: bcrypt$ or raw $2b$…).

Security notes
--------------
- Fail-closed: missing password → no access.
- String equality uses SHA-256 digests + hmac.compare_digest so unequal
  lengths never raise (raw hmac.compare_digest raises ValueError on length
  mismatch — that would 500 the login form).
"""

from __future__ import annotations

import hashlib
import hmac
import os

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


def _const_eq(a: str, b: str, *, domain: bytes = b"astrotrading") -> bool:
    """
    Constant-time string equality that tolerates unequal lengths.

    Compares SHA-256 digests so hmac.compare_digest never sees unequal input
    lengths (which would raise ValueError and break the login form).
    """
    da = hashlib.sha256(domain + b"\0" + a.encode("utf-8")).digest()
    db = hashlib.sha256(domain + b"\0" + b.encode("utf-8")).digest()
    return hmac.compare_digest(da, db)


def _verify_password(plain: str, expected: str) -> bool:
    if not expected:
        return False
    if expected.startswith("bcrypt$") or expected.startswith("$2"):
        try:
            import bcrypt

            token = expected.replace("bcrypt$", "", 1) if expected.startswith("bcrypt$") else expected
            return bool(bcrypt.checkpw(plain.encode("utf-8"), token.encode("utf-8")))
        except Exception:
            return False
    return _const_eq(plain, expected, domain=b"astrotrading-password")


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

    # Fail closed if no password configured
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
        user_ok = _const_eq(user.strip(), username_expected, domain=b"astrotrading-user")
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
