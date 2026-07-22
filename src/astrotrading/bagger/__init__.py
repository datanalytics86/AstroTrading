"""Bagger Scanner — multi-bagger candidates aligned with classic literature."""

from .engine import BaggerResult, BaggerCandidate, run_bagger_scanner
from .scoring import PILLAR_WEIGHTS, SCORE_SOURCES

__all__ = [
    "BaggerResult",
    "BaggerCandidate",
    "run_bagger_scanner",
    "PILLAR_WEIGHTS",
    "SCORE_SOURCES",
]
