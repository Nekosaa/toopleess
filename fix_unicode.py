"""Preflight helper.

Removes BOM markers and normalises line endings on all *.py files inside the
project. Prevents PyInstaller from choking on invisible characters produced by
some Windows editors. Safe to run repeatedly.
"""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent


def fix_file(path: Path) -> bool:
    try:
        raw = path.read_bytes()
    except OSError:
        return False
    changed = False
    # Strip UTF-8 BOM
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
        changed = True
    # Normalise CRLF -> LF
    if b"\r\n" in raw:
        raw = raw.replace(b"\r\n", b"\n")
        changed = True
    if b"\r" in raw:
        raw = raw.replace(b"\r", b"\n")
        changed = True
    if changed:
        path.write_bytes(raw)
    return changed


def main() -> None:
    total = 0
    fixed = 0
    for py in ROOT.rglob("*.py"):
        total += 1
        if fix_file(py):
            fixed += 1
            print(f"fixed: {py.relative_to(ROOT)}")
    print(f"fix_unicode: scanned {total}, fixed {fixed}")


if __name__ == "__main__":
    main()
