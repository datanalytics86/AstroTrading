"""Auth gate unit tests (no Streamlit runtime required for crypto helpers)."""

from __future__ import annotations

import pytest

from astrotrading.auth_gate import _const_eq, _verify_password


class TestConstEq:
    def test_equal(self):
        assert _const_eq("owner", "owner") is True

    def test_unequal_same_length(self):
        assert _const_eq("owner", "owneR") is False

    def test_unequal_length_does_not_raise(self):
        # CRITICAL regression: raw hmac.compare_digest raises ValueError on length mismatch
        assert _const_eq("a", "abcdef") is False
        assert _const_eq("toolongusername", "x") is False

    def test_empty(self):
        assert _const_eq("", "") is True
        assert _const_eq("", "x") is False


class TestVerifyPassword:
    def test_empty_expected_fail_closed(self):
        assert _verify_password("anything", "") is False

    def test_plaintext_match(self):
        assert _verify_password("secret", "secret") is True

    def test_plaintext_mismatch_length(self):
        assert _verify_password("short", "much-longer-password") is False

    def test_bcrypt_roundtrip(self):
        bcrypt = pytest.importorskip("bcrypt")
        hashed = bcrypt.hashpw(b"s3cret!", bcrypt.gensalt(rounds=4)).decode("utf-8")
        assert _verify_password("s3cret!", hashed) is True
        assert _verify_password("s3cret!", "bcrypt$" + hashed) is True
        assert _verify_password("wrong", hashed) is False
