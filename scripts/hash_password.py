#!/usr/bin/env python3
"""Generate a bcrypt hash for ASTROTRADING_PASSWORD."""

from __future__ import annotations

import getpass
import sys


def main() -> int:
    try:
        import bcrypt
    except ImportError:
        print("Install bcrypt: pip install bcrypt", file=sys.stderr)
        return 1

    pwd = getpass.getpass("Password: ")
    if not pwd:
        print("Empty password", file=sys.stderr)
        return 1
    hashed = bcrypt.hashpw(pwd.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
    print("\nSet in .env or secrets.toml:")
    print(f'ASTROTRADING_PASSWORD=bcrypt${hashed}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
