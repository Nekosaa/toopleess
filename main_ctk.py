"""Prizma Studio - главное окно.

Профессиональное боковое меню с 3-цветным градиентом
(бирюзовый -> индиго -> фиолетовый) и сгруппированной навигацией.
"""
from __future__ import annotations

import sys
from pathlib import Path
from tkinter import filedialog

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import customtkinter as ctk

from core import __app_name__, __author__, __version__
from core.config import config
from core.i18n import i18n
from core.ctk_theme import (
    BG_MAIN, BG_CARD, BG_SIDEBAR, BG_INPUT,
    ACCENT_CYAN, ACCENT_CYAN_HOVER, ACCENT_INDIGO, ACCENT_INDIGO_HOVER,
    ACCENT_PURPLE, ACCENT_PURPLE_HOVER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    BORDER, BORDER_SOFT, SUCCESS, WARNING, ERROR,
    GRAD_START, GRAD_MID, GRAD_END, apply_ctk_theme,
)
from core.ui import grad_ctkimage, GradientDivider, NavButton
from modules.pdf_tools_tab_ctk import PdfToolsFrameCTk
from modules.psd_tools_tab_ctk import PsdToolsFrameCTk


FONT_TITLE = ("Segoe UI Semibold", 22)
FONT_TAG = ("Segoe UI", 11)
FONT_H = ("Segoe UI Semibold", 13)
FONT = ("Segoe UI", 12)
FONT_MONO = ("Consolas", 11)
FONT_SECTION = ("Segoe UI Semibold", 10)
FONT_BRAND = ("Segoe UI Semibold", 16)
FONT_BRAND_SUB = ("Segoe UI", 10)

# Иконки Segoe Fluent Icons / Segoe MDL2 Assets (доступны на Windows 10/11)
ICON_PDF = "\uE8A5"       # Document
ICON_PSD = "\uE91B"       # Photo
ICON_SETTINGS = "\uE713"  # Settings (gear)
ICON_ABOUT = "\uE946"     # Info
ICON_MOON = "\uE708"      # Night / dark theme
ICON_SUN = "\uE706"       # Brightness / light theme


def _t(key: str, fallback: str = "") -> str:
    try:
        val = i18n.t(key)
        return val if val and val != key else (fallback or key)
    except Exception:
        return fallback or key


# ---------------------------------------------------------------------------
# Журнал
# ---------------------------------------------------------------------------
class LogPanel(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=BG_CARD, corner_radius=12,
                         border_width=1, border_color=BORDER)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 6))
        head.grid_columnconfigure(0, weight=1)

        self._title = ctk.CTkLabel(head, text=_t("log.title", "Журнал").upper(),
                                   font=FONT_H, text_color=TEXT_SECONDARY)
        self._title.grid(row=0, column=0, sticky="w")

        self._clear_btn = ctk.CTkButton(
            head, text=_t("log.clear", "Очистить"),
            command=self.clear, width=100, height=30,
            font=FONT, fg_color="transparent",
            hover_color=BG_INPUT, text_color=TEXT_PRIMARY,
            border_width=1, border_color=BORDER, corner_radius=8,
        )
        self._clear_btn.grid(row=0, column=1, sticky="e")

        self._text = ctk.CTkTextbox(
            self, height=130, corner_radius=8,
            fg_color=BG_INPUT, border_color=BORDER, border_width=1,
            text_color=TEXT_PRIMARY, font=FONT_MONO,
        )
        self._text.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 14))
        self._text.configure(state="disabled")
        i18n.subscribe(self._retranslate)

    def _retranslate(self):
        self._title.configure(text=_t("log.title", "Журнал").upper())
        self._clear_btn.configure(text=_t("log.clear", "Очистить"))

    def log(self, message, level="info"):
        prefix = {"info": "*", "warn": "!", "error": "x", "ok": "+"}.get(level, "*")
        self._text.configure(state="normal")
        self._text.insert("end", f"  {prefix}  {message}\n")
        self._text.see("end")
        self._text.configure(state="disabled")

    def clear(self):
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(state="disabled")


# ---------------------------------------------------------------------------
# Настройки
# ---------------------------------------------------------------------------
class SettingsFrame(ctk.CTkFrame):
    def __init__(self, master, on_theme_change):
        super().__init__(master, fg_color="transparent")
        self._on_theme_change = on_theme_change
        card = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12,
                            border_width=1, border_color=BORDER)
        card.pack(fill="both", expand=True)
        card.grid_columnconfigure(1, weight=1)
        r = 0
        ctk.CTkLabel(card, text=_t("settings.language", "Язык"), font=FONT_H,
                     text_color=TEXT_PRIMARY).grid(row=r, column=0, sticky="w",
                                                   padx=20, pady=(20, 6))
        self._lang = ctk.CTkOptionMenu(
            card, values=["ru", "en"], command=self._apply_lang,
            width=140, fg_color=BG_INPUT, button_color=ACCENT_INDIGO,
            button_hover_color=ACCENT_INDIGO_HOVER, corner_radius=8,
        )
        self._lang.set(config.get("language", "ru"))
        self._lang.grid(row=r, column=1, sticky="w", padx=6, pady=(20, 6)); r += 1

        ctk.CTkLabel(card, text=_t("settings.theme", "Тема"), font=FONT_H,
                     text_color=TEXT_PRIMARY).grid(row=r, column=0, sticky="w",
                                                   padx=20, pady=6)
        self._theme = ctk.CTkOptionMenu(
            card, values=["dark", "light", "system"],
            command=self._apply_theme, width=140, fg_color=BG_INPUT,
            button_color=ACCENT_INDIGO, button_hover_color=ACCENT_INDIGO_HOVER,
            corner_radius=8,
        )
        self._theme.set(config.get("theme", "dark"))
        self._theme.grid(row=r, column=1, sticky="w", padx=6, pady=6); r += 1

        ctk.CTkLabel(card, text=_t("settings.paths", "Папки по умолчанию"),
                     font=FONT_H, text_color=TEXT_SECONDARY).grid(
            row=r, column=0, columnspan=3, sticky="w",
            padx=20, pady=(18, 8)); r += 1
        self._row_path(card, _t("settings.pdf_dir", "PDF:"), "pdf_last_dir", r); r += 1
        self._row_path(card, _t("settings.psd_in", "PSD (вход):"), "psd_in_dir", r); r += 1
        self._row_path(card, _t("settings.psd_out", "PSD (выход):"), "psd_out_dir", r); r += 1

        ctk.CTkLabel(card, text=_t("settings.depth", "Глубина Smart Object"),
                     font=FONT_H, text_color=TEXT_PRIMARY).grid(
            row=r, column=0, sticky="w", padx=20, pady=(18, 20))
        self._depth = ctk.CTkOptionMenu(
            card, values=[str(i) for i in range(1, 11)],
            command=self._apply_depth, width=90, fg_color=BG_INPUT,
            button_color=ACCENT_INDIGO, button_hover_color=ACCENT_INDIGO_HOVER,
            corner_radius=8,
        )
        self._depth.set(str(config.get("smart_object_depth", 3)))
        self._depth.grid(row=r, column=1, sticky="w", padx=6, pady=(18, 20))

    def _row_path(self, card, label, cfg_key, row):
        ctk.CTkLabel(card, text=label, font=FONT, text_color=TEXT_PRIMARY).grid(
            row=row, column=0, sticky="w", padx=20, pady=4)
        var = ctk.StringVar(value=config.get(cfg_key) or "")
        var.trace_add("write", lambda *_: config.set(cfg_key, var.get()))
        ctk.CTkEntry(card, textvariable=var, fg_color=BG_INPUT,
                     border_color=BORDER, corner_radius=8, height=34).grid(
            row=row, column=1, sticky="ew", padx=6, pady=4)

        def pick():
            chosen = filedialog.askdirectory(initialdir=var.get() or str(Path.home()))
            if chosen:
                var.set(chosen)

        ctk.CTkButton(card, text=_t("common.browse", "Обзор..."), command=pick,
                      width=100, height=34, fg_color="transparent",
                      hover_color=BG_INPUT, text_color=TEXT_PRIMARY,
                      border_width=1, border_color=BORDER, corner_radius=8).grid(
            row=row, column=2, sticky="w", padx=(6, 20), pady=4)

    def _apply_lang(self, value):
        config.set("language", value); i18n.set_language(value)

    def _apply_theme(self, value):
        config.set("theme", value); self._on_theme_change(value)

    def _apply_depth(self, value):
        config.set("smart_object_depth", int(value))


# ---------------------------------------------------------------------------
# О программе
# ---------------------------------------------------------------------------
class AboutFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        card = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12,
                            border_width=1, border_color=BORDER)
        card.pack(fill="both", expand=True)

        # Крупный градиентный логотип
        logo_wrap = ctk.CTkFrame(card, fg_color="transparent")
        logo_wrap.pack(anchor="w", padx=24, pady=(24, 4))
        logo_lbl = ctk.CTkLabel(logo_wrap, text="P",
                                font=("Segoe UI Black", 26),
                                text_color="#FFFFFF", width=56, height=56)
        limg = grad_ctkimage(56, 56, GRAD_START, GRAD_MID, GRAD_END, radius=16)
        if limg is not None:
            logo_lbl.configure(image=limg, compound="center")
            logo_lbl._grad = limg
        logo_lbl.pack(side="left")
        ctk.CTkLabel(logo_wrap, text=__app_name__,
                     font=("Segoe UI Semibold", 24),
                     text_color=TEXT_PRIMARY).pack(side="left", padx=(14, 0))

        ctk.CTkLabel(card, text=f"Версия {__version__}", font=FONT,
                     text_color=TEXT_SECONDARY).pack(anchor="w", padx=24, pady=2)
        ctk.CTkLabel(card, text=f"Автор: {__author__}", font=FONT,
                     text_color=TEXT_SECONDARY).pack(anchor="w", padx=24, pady=2)
        ctk.CTkLabel(card, text="Работа с PDF и PSD в одном окне.",
                     font=FONT, text_color=TEXT_MUTED).pack(
            anchor="w", padx=24, pady=(14, 24))


# ---------------------------------------------------------------------------
# Главное окно (sidebar layout)
# ---------------------------------------------------------------------------
class MainApp:
    # Группированное меню:
    #   секция -> список пунктов (key, i18n_key, fallback, subtitle, icon)
    SIDEBAR_SECTIONS = [
        ("ИНСТРУМЕНТЫ", [
            ("pdf",      "tab.pdf",      "PDF Tools",  "Конвертация и обработка PDF",       ICON_PDF),
            ("psd",      "tab.psd",      "PSD Tools",  "Слои и Smart Object",               ICON_PSD),
        ]),
        ("СИСТЕМА", [
            ("settings", "tab.settings", "Настройки",  "Язык, тема и папки по умолчанию",   ICON_SETTINGS),
            ("about",    "tab.about",    "О программе","Информация о Prizma Studio",        ICON_ABOUT),
        ]),
    ]

    def __init__(self, root: ctk.CTk):
        self.root = root
        apply_ctk_theme(root, mode=config.get("theme", "dark"))
        root.title(f"{__app_name__} - v{__version__}")
        try:
            root.geometry(config.get("window_geometry") or "1240x860")
        except Exception:
            root.geometry("1240x860")
        root.minsize(1060, 680)
        root.configure(fg_color=BG_MAIN)
        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(0, weight=1)

        self._current = "pdf"
        self._log_fn = lambda msg, level="info": self.log_panel.log(msg, level)

        self._nav: dict[str, NavButton] = {}
        self._sections: dict[str, ctk.CTkLabel] = {}

        self._build_sidebar()
        self._build_main()

        i18n.subscribe(self._retranslate)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- Боковое меню --------------------------------------------------
    def _build_sidebar(self):
        SIDEBAR_W = 260

        sb = ctk.CTkFrame(self.root, fg_color=BG_SIDEBAR, corner_radius=0,
                          width=SIDEBAR_W, border_width=0)
        sb.grid(row=0, column=0, sticky="nsw")
        sb.grid_propagate(False)
        sb.grid_columnconfigure(0, weight=1)
        # rows: 0 brand | 1 divider | 2 nav | 3 spacer | 4 footer
        sb.grid_rowconfigure(3, weight=1)

        # --- Бренд ---
        brand = ctk.CTkFrame(sb, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=20, pady=(22, 14))
        brand.grid_columnconfigure(1, weight=1)

        logo = ctk.CTkLabel(brand, text="P",
                            font=("Segoe UI Black", 20),
                            text_color="#FFFFFF", width=44, height=44)
        limg = grad_ctkimage(44, 44, GRAD_START, GRAD_MID, GRAD_END, radius=13)
        if limg is not None:
            logo.configure(image=limg, compound="center")
            logo._grad = limg
        logo.grid(row=0, column=0, rowspan=2, padx=(0, 12))
        ctk.CTkLabel(brand, text=__app_name__, font=FONT_BRAND,
                     text_color=TEXT_PRIMARY).grid(row=0, column=1, sticky="sw")
        ctk.CTkLabel(brand, text="PDF + PSD Studio", font=FONT_BRAND_SUB,
                     text_color=TEXT_MUTED).grid(row=1, column=1, sticky="nw")

        # --- Разделитель-градиент под брендом ---
        GradientDivider(sb, GRAD_START, GRAD_MID, GRAD_END, height=2).grid(
            row=1, column=0, sticky="ew", padx=20, pady=(0, 14))

        # --- Секции с пунктами ---
        nav = ctk.CTkFrame(sb, fg_color="transparent")
        nav.grid(row=2, column=0, sticky="new", padx=14)
        nav.grid_columnconfigure(0, weight=1)

        for si, (section_title, items) in enumerate(self.SIDEBAR_SECTIONS):
            top_pad = 0 if si == 0 else 18
            sec_lbl = ctk.CTkLabel(
                nav, text=section_title, font=FONT_SECTION,
                text_color=TEXT_MUTED, anchor="w",
            )
            sec_lbl.grid(sticky="w", padx=10, pady=(top_pad, 8))
            self._sections[section_title] = sec_lbl

            for key, i18n_key, fallback, _sub, icon in items:
                btn = NavButton(
                    nav, text=_t(i18n_key, fallback),
                    c1=GRAD_START, c2=GRAD_MID, c3=GRAD_END,
                    icon=icon, width=SIDEBAR_W - 28, height=42,
                    command=lambda k=key: self._select(k),
                )
                btn.grid(sticky="ew", pady=2)
                self._nav[key] = btn

        # --- Низ: язык + переключатель темы ---
        # Тонкая линия-разделитель над футером
        sep = ctk.CTkFrame(sb, fg_color=BORDER_SOFT, height=1,
                           corner_radius=0, border_width=0)
        sep.grid(row=4, column=0, sticky="new", padx=18)

        bottom = ctk.CTkFrame(sb, fg_color="transparent")
        bottom.grid(row=4, column=0, sticky="ew", padx=18, pady=(14, 18))
        bottom.grid_columnconfigure(0, weight=1)

        self._lang = ctk.CTkOptionMenu(
            bottom, values=["ru", "en"], command=self._on_lang,
            width=110, height=32,
            fg_color=BG_INPUT, button_color=ACCENT_INDIGO,
            button_hover_color=ACCENT_INDIGO_HOVER, corner_radius=8,
        )
        self._lang.set(config.get("language", "ru"))
        self._lang.grid(row=0, column=0, sticky="w")

        self._theme_btn = ctk.CTkButton(
            bottom, text=self._theme_icon(), width=40, height=32, corner_radius=8,
            fg_color=BG_INPUT, hover_color=BORDER,
            text_color=TEXT_PRIMARY,
            font=(self._icon_font(), 15),
            command=self._toggle_theme,
        )
        self._theme_btn.grid(row=0, column=1, sticky="e", padx=(8, 0))

    # ---- Основная область ---------------------------------------------
    def _build_main(self):
        main = ctk.CTkFrame(self.root, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=(18, 22), pady=18)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        # Заголовок раздела
        top = ctk.CTkFrame(main, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        top.grid_columnconfigure(0, weight=1)
        self._page_title = ctk.CTkLabel(top, text="", font=FONT_TITLE,
                                        text_color=TEXT_PRIMARY)
        self._page_title.grid(row=0, column=0, sticky="w")
        self._page_sub = ctk.CTkLabel(top, text="", font=FONT_TAG,
                                      text_color=TEXT_MUTED)
        self._page_sub.grid(row=1, column=0, sticky="w")

        # Контент
        self._content = ctk.CTkFrame(main, fg_color="transparent")
        self._content.grid(row=1, column=0, sticky="nsew")
        self._content.grid_columnconfigure(0, weight=1)
        self._content.grid_rowconfigure(0, weight=1)

        # Журнал
        self.log_panel = LogPanel(main)
        self.log_panel.grid(row=2, column=0, sticky="ew", pady=(14, 6))

        # Статус
        status = ctk.CTkFrame(main, fg_color="transparent")
        status.grid(row=3, column=0, sticky="ew")
        status.grid_columnconfigure(0, weight=1)
        self._status = ctk.CTkLabel(status, text=_t("status.ready", "Готово"),
                                    font=FONT, text_color=TEXT_MUTED)
        self._status.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(status, text=f"v{__version__}", font=FONT,
                     text_color=TEXT_MUTED).grid(row=0, column=1, sticky="e")

        # Страницы
        self._frames = {
            "pdf": PdfToolsFrameCTk(self._content, log=self._log_fn),
            "psd": PsdToolsFrameCTk(self._content, log=self._log_fn),
            "settings": SettingsFrame(self._content,
                                      on_theme_change=self._change_theme),
            "about": AboutFrame(self._content),
        }
        for f in self._frames.values():
            f.grid(row=0, column=0, sticky="nsew")

        self._select("pdf")

    # ---- Утилиты -------------------------------------------------------
    @staticmethod
    def _icon_font() -> str:
        try:
            import tkinter.font as tkfont
            families = set(tkfont.families())
            for f in ("Segoe Fluent Icons", "Segoe MDL2 Assets"):
                if f in families:
                    return f
        except Exception:
            pass
        return "Segoe UI"

    def _theme_icon(self) -> str:
        return ICON_SUN if config.get("theme", "dark") == "dark" else ICON_MOON

    # ---- Логика --------------------------------------------------------
    def _select(self, key: str):
        self._current = key
        for k, btn in self._nav.items():
            btn.set_active(k == key)
        for _title, items in self.SIDEBAR_SECTIONS:
            for pkey, i18n_key, fb, sub, _ic in items:
                if pkey == key:
                    self._page_title.configure(text=_t(i18n_key, fb))
                    self._page_sub.configure(text=sub)
                    break
        frame = self._frames.get(key)
        if frame:
            frame.tkraise()

    def _on_lang(self, value):
        config.set("language", value); i18n.set_language(value)

    def _toggle_theme(self):
        new = "light" if config.get("theme", "dark") == "dark" else "dark"
        config.set("theme", new)
        apply_ctk_theme(self.root, mode=new)
        self._theme_btn.configure(text=self._theme_icon())

    def _change_theme(self, mode):
        apply_ctk_theme(self.root, mode=mode)
        self._theme_btn.configure(text=self._theme_icon())

    def _retranslate(self):
        self._status.configure(text=_t("status.ready", "Готово"))
        for _title, items in self.SIDEBAR_SECTIONS:
            for key, i18n_key, fb, _sub, _icon in items:
                if key in self._nav:
                    self._nav[key].set_text(_t(i18n_key, fb))
        self._select(self._current)

    def _on_close(self):
        try:
            config.set("window_geometry", self.root.geometry())
        finally:
            self.root.destroy()


def main():
    root = ctk.CTk()
    MainApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
