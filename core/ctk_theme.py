"""Prizma Studio - тема оформления (CustomTkinter).

Профессиональный тёмный стиль: графит + единый синий/индиго акцент.
Управляйте всем видом приложения, меняя значения в блоке ПАЛИТРА.
"""
from __future__ import annotations

import customtkinter as ctk

# ---------------------------------------------------------------------------
# ПАЛИТРА (меняйте только hex-значения — имена констант трогать не нужно)
# ---------------------------------------------------------------------------

# Фон и поверхности
BG_MAIN             = "#0e1116"   # основной фон окна
BG_GRADIENT_START   = "#12151c"   # верх шапки
BG_GRADIENT_END     = "#0e1116"   # низ шапки
BG_CARD             = "#171b22"   # карточки / тулбары / панели
BG_SIDEBAR          = "#13161d"   # боковая панель
BG_INPUT            = "#1e232c"   # поля ввода

# Границы / разделители (аккуратные, вместо яркого свечения)
BORDER              = "#262b34"
NEON_GLOW           = "#262b34"

# Акценты (бирюзовый + фиолетовый)
ACCENT_CYAN         = "#2dd4bf"   # основной акцент (бирюзовый)
ACCENT_CYAN_HOVER   = "#14b8a6"
ACCENT_PURPLE       = "#8b5cf6"   # вторичный (фиолетовый)
ACCENT_PURPLE_HOVER = "#7c3aed"

# Градиент-перелив (бирюза -> фиолетовый)
GRAD_START          = "#2dd4bf"
GRAD_END            = "#8b5cf6"

# Текст
TEXT_PRIMARY        = "#e6edf3"
TEXT_SECONDARY      = "#9aa4b2"
TEXT_MUTED          = "#6b7280"

# Статусы
SUCCESS             = "#22c55e"
WARNING             = "#f59e0b"
ERROR               = "#ef4444"
INFO                = "#3b82f6"

# Радиусы / отступы для единообразия
RADIUS              = 8
RADIUS_CARD         = 12


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
            "fg_color": pair(ACCENT_CYAN),
            "hover_color": pair(ACCENT_CYAN_HOVER),
            "text_color": pair("#ffffff"),
            "text_color_disabled": pair(TEXT_MUTED),
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
                    "button_color": pair(ACCENT_CYAN),
                    "button_hover_color": pair(ACCENT_CYAN_HOVER),
                    "border_color": pair(BORDER),
                    "text_color": pair(TEXT_PRIMARY),
                    "corner_radius": RADIUS,
                })

        if "CTkTabview" in t:
            t["CTkTabview"].update({
                "fg_color": pair(BG_CARD),
                "segmented_button_fg_color": pair(BG_SIDEBAR),
                "segmented_button_selected_color": pair(ACCENT_CYAN),
                "segmented_button_selected_hover_color": pair(ACCENT_CYAN_HOVER),
                "segmented_button_unselected_color": pair(BG_SIDEBAR),
                "segmented_button_unselected_hover_color": pair(BORDER),
                "text_color": pair(TEXT_PRIMARY),
            })

        if "CTkSegmentedButton" in t:
            t["CTkSegmentedButton"].update({
                "fg_color": pair(BG_SIDEBAR),
                "selected_color": pair(ACCENT_CYAN),
                "selected_hover_color": pair(ACCENT_CYAN_HOVER),
                "unselected_color": pair(BG_SIDEBAR),
                "unselected_hover_color": pair(BORDER),
                "text_color": pair(TEXT_PRIMARY),
            })

        for key in ("CTkScrollbar", "CTkCheckBox", "CTkRadioButton",
                    "CTkSwitch", "CTkSlider", "CTkProgressBar"):
            if key in t:
                for ck in ("button_color", "progress_color", "fg_color"):
                    if ck in t[key]:
                        t[key][ck] = pair(ACCENT_CYAN)
                if "button_hover_color" in t[key]:
                    t[key]["button_hover_color"] = pair(ACCENT_CYAN_HOVER)
    except Exception:
        # разные версии CustomTkinter — не падаем, применяем что смогли
        pass


def apply_ctk_theme(root=None, mode: str = "dark", *args, **kwargs) -> None:
    """Применяет профессиональную тему ко всему приложению.

    Вызывается из main_ctk.py, безопасно принимает любые доп. аргументы.
    """
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
