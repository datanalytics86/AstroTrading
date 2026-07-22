"""
Shared import bootstrap for Streamlit pages (local + Streamlit Cloud).

Ensures `src/` is on sys.path so `import astrotrading` works even when the
package is not installed editable (common Cloud pitfall).
"""

from __future__ import annotations

import sys
from pathlib import Path


def ensure_src_on_path() -> Path:
    """
    Insert the project `src/` directory on sys.path (idempotent).

    Layout:
      <repo>/app/bootstrap.py          → parents[1] = repo
      <repo>/app/pages/*.py            → should import this module first
      <repo>/src/astrotrading/...
    """
    here = Path(__file__).resolve().parent  # .../app
    repo = here.parent  # .../repo root
    src = repo / "src"

    candidates = [
        src,
        Path.cwd() / "src",
        Path.cwd(),
    ]
    # Streamlit Cloud: /mount/src/<appname>
    for p in candidates:
        p = p.resolve()
        if not p.is_dir():
            continue
        marker = p / "astrotrading"
        # either src/astrotrading or repo with flat package
        if marker.is_dir() or (p / "astrology").is_dir():
            sp = str(p)
            if sp not in sys.path:
                sys.path.insert(0, sp)
            return p

    # Fallback: always prefer repo/src if it exists
    if src.is_dir():
        sp = str(src.resolve())
        if sp not in sys.path:
            sys.path.insert(0, sp)
        return src.resolve()

    return Path.cwd()
