"""Prizma Studio - тема оформления (CustomTkinter).

Профессиональный тёмный стиль:
  - Фон: глубокий графит с лёгким холодным подтоном
  - Акценты: 3-цветный градиент бирюзовый -> индиго -> фиолетовый
Меняйте только hex-значения в блоке ПАЛИТРА.
"""
from __future__ import annotations

import customtkinter as ctk

# ---------------------------------------------------------------------------
# ПАЛИТРА
# ---------------------------------------------------------------------------

# Фон и поверхности
BG_MAIN = "#0B0E14"
BG_GRADIENT_START = "#12151C"
BG_GRADIENT_END = "#0B0E14"
BG_CARD = "#161A22"
BG_CARD_HOVER = "#1B2029"
BG_SIDEBAR = "#0F131A"
BG_INPUT = "#1D222C"

# Границы
BORDER = "#242A35"
BORDER_SOFT = "#1E232D"
NEON_GLOW = "#242A35"

# Акценты — 3-стоп градиент
ACCENT_CYAN = "#2DD4BF"
ACCENT_CYAN_HOVER = "#14B8A6"
ACCENT_INDIGO = "#6366F1"
ACCENT_INDIGO_HOVER = "#4F46E5"
ACCENT_PURPLE = "#A855F7"
ACCENT_PURPLE_HOVER = "#9333EA"

# Градиент-перелив: бирюза -> индиго -> фиолет
GRAD_START = ACCENT_CYAN
GRAD_MID = ACCENT_INDIGO
GRAD_MIDDLE = ACCENT_INDIGO      # alias для совместимости
GRAD_END = ACCENT_PURPLE

# Текст
TEXT_PRIMARY = "#E6EDF3"
TEXT_SECONDARY = "#A0AABA"
TEXT_MUTED = "#6B7382"
TEXT_DISABLED = "#4A5261"

# Статусы
SUCCESS = "#22C55E"
WARNING = "#F59E0B"
ERROR = "#EF4444"
INFO = "#38BDF8"

# Радиусы
RADIUS = 8
RADIUS_CARD = 12
RADIUS_PILL = 999


def _override_theme() -> None:
    """Глобально задаёт стиль стандартных виджетов CustomTkinter."""
    try:
        t = ctk.ThemeManager.theme
    except Exception:
        return

    def pair(c):
        return [c, c]

    try:
        t["CTk"]["fg_color"] = pair(BG_MAIN)
        t["CTkToplevel"]["fg_color"] = pair(BG_MAIN)

        t["CTkFrame"].update({
            "fg_color": pair(BG_CARD),
            "top_fg_color": pair(BG_CARD),
            "border_color": pair(BORDER),
            "corner_radius": RADIUS_CARD,
            "border_width": 1,
        })

        t["CTkButton"].update({
            "fg_color": pair(ACCENT_INDIGO),
            "hover_color": pair(ACCENT_INDIGO_HOVER),
            "text_color": pair("#FFFFFF"),
            "text_color_disabled": pair(TEXT_DISABLED),
            "border_color": pair(BORDER),
            "corner_radius": RADIUS,
            "border_width": 0,
        })

        t["CTkLabel"].update({
            "fg_color": "transparent",
            "text_color": pair(TEXT_PRIMARY),
        })

        t["CTkEntry"].update({
            "fg_color": pair(BG_INPUT),
            "border_color": pair(BORDER),
            "text_color": pair(TEXT_PRIMARY),
            "placeholder_text_color": pair(TEXT_MUTED),
            "corner_radius": RADIUS,
            "border_width": 1,
        })

        for key in ("CTkComboBox", "CTkOptionMenu"):
            if key in t:
                t[key].update({
                    "fg_color": pair(BG_INPUT),
                    "button_color": pair(ACCENT_INDIGO),
                    "button_hover_color": pair(ACCENT_INDIGO_HOVER),
                    "border_color": pair(BORDER),
                    "text_color": pair(TEXT_PRIMARY),
                    "corner_radius": RADIUS,
                })

        if "CTkTabview" in t:
            t["CTkTabview"].update({
                "fg_color": pair(BG_CARD),
                "segmented_button_fg_color": pair(BG_SIDEBAR),
                "segmented_button_selected_color": pair(ACCENT_INDIGO),
                "segmented_button_selected_hover_color": pair(ACCENT_INDIGO_HOVER),
                "segmented_button_unselected_color": pair(BG_SIDEBAR),
                "segmented_button_unselected_hover_color": pair(BORDER),
                "text_color": pair(TEXT_PRIMARY),
            })

        if "CTkSegmentedButton" in t:
            t["CTkSegmentedButton"].update({
                "fg_color": pair(BG_SIDEBAR),
                "selected_color": pair(ACCENT_INDIGO),
                "selected_hover_color": pair(ACCENT_INDIGO_HOVER),
                "unselected_color": pair(BG_SIDEBAR),
                "unselected_hover_color": pair(BORDER),
                "text_color": pair(TEXT_PRIMARY),
            })

        for key in ("CTkScrollbar", "CTkCheckBox", "CTkRadioButton",
                    "CTkSwitch", "CTkSlider", "CTkProgressBar"):
            if key in t:
                for ck in ("button_color", "progress_color", "fg_color"):
                    if ck in t[key]:
                        t[key][ck] = pair(ACCENT_INDIGO)
                if "button_hover_color" in t[key]:
                    t[key]["button_hover_color"] = pair(ACCENT_INDIGO_HOVER)
    except Exception:
        pass


def apply_ctk_theme(root=None, mode: str = "dark", *args, **kwargs) -> None:
    """Применяет тему ко всему приложению."""
    try:
        ctk.set_appearance_mode(mode if mode in ("light", "dark", "system") else "dark")
    except Exception:
        ctk.set_appearance_mode("dark")
    try:
        ctk.set_default_color_theme("dark-blue")
    except Exception:
        pass

    _override_theme()

    if root is not None:
        try:
            root.configure(fg_color=BG_MAIN)
        except Exception:
            try:
                root.configure(bg=BG_MAIN)
            except Exception:
                pass
