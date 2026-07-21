"""Theme helper: applies sv-ttk light/dark based on user choice or OS setting."""
from __future__ import annotations

import sys
import tkinter as tk


def _detect_system_theme() -> str:
    """Return 'dark' or 'light' based on the current OS setting."""
    # Windows registry gives the most reliable indicator.
    if sys.platform.startswith("win"):
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return "light" if value == 1 else "dark"
        except OSError:
            pass
    # Cross-platform fallback.
    try:
        import darkdetect  # type: ignore
        detected = darkdetect.theme()
        if isinstance(detected, str):
            return detected.lower()
    except Exception:
        pass
    return "light"


def apply_theme(root: tk.Misc, mode: str) -> str:
    """Apply the requested theme ('system' | 'light' | 'dark').

    Returns the effective theme actually applied ('light' or 'dark').
    """
    import sv_ttk
    effective = _detect_system_theme() if mode == "system" else mode
    if effective not in ("light", "dark"):
        effective = "light"
    sv_ttk.set_theme(effective, root)
    return effective
