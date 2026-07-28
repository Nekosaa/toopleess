"""Prizma Studio - главное окно (бирюзово-фиолетовый градиент)."""
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
    ACCENT_CYAN, ACCENT_CYAN_HOVER, ACCENT_PURPLE,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    BORDER, SUCCESS, WARNING, ERROR,
    GRAD_START, GRAD_END, apply_ctk_theme,
)
from core.ui import grad_ctkimage, GradientDivider
from modules.pdf_tools_tab_ctk import PdfToolsFrameCTk
from modules.psd_tools_tab_ctk import PsdToolsFrameCTk

FONT_TITLE = ("Segoe UI Semibold", 20)
FONT_TAG = ("Segoe UI", 11)
FONT_H = ("Segoe UI Semibold", 13)
FONT = ("Segoe UI", 12)
FONT_MONO = ("Consolas", 11)


def _t(key: str, fallback: str = "") -> str:
    try:
        val = i18n.t(key)
        return val if val and val != key else (fallback or key)
    except Exception:
        return fallback or key


class LogPanel(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=BG_CARD, corner_radius=12,
                         border_width=1, border_color=BORDER)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))
        head.grid_columnconfigure(0, weight=1)
        self._title = ctk.CTkLabel(head, text=_t("log.title", "Журнал").upper(),
                                   font=FONT_H, text_color=TEXT_SECONDARY)
        self._title.grid(row=0, column=0, sticky="w")
        self._clear_btn = ctk.CTkButton(head, text=_t("log.clear", "Очистить"),
                                        command=self.clear, width=100, height=30,
                                        font=FONT, fg_color="transparent",
                                        hover_color=BG_INPUT, text_color=TEXT_PRIMARY,
                                        border_width=1, border_color=BORDER, corner_radius=8)
        self._clear_btn.grid(row=0, column=1, sticky="e")
        self._text = ctk.CTkTextbox(self, height=140, corner_radius=8,
                                    fg_color=BG_INPUT, border_color=BORDER, border_width=1,
                                    text_color=TEXT_PRIMARY, font=FONT_MONO)
        self._text.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 12))
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
                     text_color=TEXT_PRIMARY).grid(row=r, column=0, sticky="w", padx=20, pady=(20, 6))
        self._lang = ctk.CTkOptionMenu(card, values=["ru", "en"], command=self._apply_lang,
                                       width=140, fg_color=BG_INPUT, button_color=ACCENT_CYAN,
                                       button_hover_color=ACCENT_CYAN_HOVER, corner_radius=8)
        self._lang.set(config.get("language", "ru"))
        self._lang.grid(row=r, column=1, sticky="w", padx=6, pady=(20, 6)); r += 1
        ctk.CTkLabel(card, text=_t("settings.theme", "Тема"), font=FONT_H,
                     text_color=TEXT_PRIMARY).grid(row=r, column=0, sticky="w", padx=20, pady=6)
        self._theme = ctk.CTkOptionMenu(card, values=["dark", "light", "system"],
                                        command=self._apply_theme, width=140, fg_color=BG_INPUT,
                                        button_color=ACCENT_CYAN, button_hover_color=ACCENT_CYAN_HOVER,
                                        corner_radius=8)
        self._theme.set(config.get("theme", "dark"))
        self._theme.grid(row=r, column=1, sticky="w", padx=6, pady=6); r += 1
        ctk.CTkLabel(card, text=_t("settings.paths", "Папки по умолчанию"), font=FONT_H,
                     text_color=TEXT_SECONDARY).grid(row=r, column=0, columnspan=3, sticky="w",
                                                     padx=20, pady=(18, 8)); r += 1
        self._row_path(card, _t("settings.pdf_dir", "PDF:"), "pdf_last_dir", r); r += 1
        self._row_path(card, _t("settings.psd_in", "PSD (вход):"), "psd_in_dir", r); r += 1
        self._row_path(card, _t("settings.psd_out", "PSD (выход):"), "psd_out_dir", r); r += 1
        ctk.CTkLabel(card, text=_t("settings.depth", "Глубина Smart Object"), font=FONT_H,
                     text_color=TEXT_PRIMARY).grid(row=r, column=0, sticky="w", padx=20, pady=(18, 20))
        self._depth = ctk.CTkOptionMenu(card, values=[str(i) for i in range(1, 11)],
                                        command=self._apply_depth, width=90, fg_color=BG_INPUT,
                                        button_color=ACCENT_CYAN, button_hover_color=ACCENT_CYAN_HOVER,
                                        corner_radius=8)
        self._depth.set(str(config.get("smart_object_depth", 3)))
        self._depth.grid(row=r, column=1, sticky="w", padx=6, pady=(18, 20))

    def _row_path(self, card, label, cfg_key, row):
        ctk.CTkLabel(card, text=label, font=FONT, text_color=TEXT_PRIMARY).grid(
            row=row, column=0, sticky="w", padx=20, pady=4)
        var = ctk.StringVar(value=config.get(cfg_key) or "")
        var.trace_add("write", lambda *_: config.set(cfg_key, var.get()))
        ctk.CTkEntry(card, textvariable=var, fg_color=BG_INPUT, border_color=BORDER,
                     corner_radius=8, height=34).grid(row=row, column=1, sticky="ew", padx=6, pady=4)

        def pick():
            chosen = filedialog.askdirectory(initialdir=var.get() or str(Path.home()))
            if chosen:
                var.set(chosen)
        ctk.CTkButton(card, text=_t("common.browse", "Обзор..."), command=pick, width=100,
                      height=34, fg_color="transparent", hover_color=BG_INPUT, text_color=TEXT_PRIMARY,
                      border_width=1, border_color=BORDER, corner_radius=8).grid(
            row=row, column=2, sticky="w", padx=(6, 20), pady=4)

    def _apply_lang(self, value):
        config.set("language", value); i18n.set_language(value)

    def _apply_theme(self, value):
        config.set("theme", value); self._on_theme_change(value)

    def _apply_depth(self, value):
        config.set("smart_object_depth", int(value))


class AboutFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        card = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12,
                            border_width=1, border_color=BORDER)
        card.pack(fill="both", expand=True)
        ctk.CTkLabel(card, text=__app_name__, font=("Segoe UI Semibold", 24),
                     text_color=ACCENT_CYAN).pack(anchor="w", padx=24, pady=(24, 4))
        ctk.CTkLabel(card, text=f"Версия {__version__}", font=FONT,
                     text_color=TEXT_SECONDARY).pack(anchor="w", padx=24, pady=2)
        ctk.CTkLabel(card, text=f"Автор: {__author__}", font=FONT,
                     text_color=TEXT_SECONDARY).pack(anchor="w", padx=24, pady=2)
        ctk.CTkLabel(card, text="Работа с PDF и PSD в одном окне.", font=FONT,
                     text_color=TEXT_MUTED).pack(anchor="w", padx=24, pady=(14, 24))


class MainApp:
    def __init__(self, root: ctk.CTk):
        self.root = root
        apply_ctk_theme(root, mode=config.get("theme", "dark"))
        root.title(f"{__app_name__} - v{__version__}")
        try:
            root.geometry(config.get("window_geometry") or "1200x820")
        except Exception:
            root.geometry("1200x820")
        root.minsize(980, 640)
        root.configure(fg_color=BG_MAIN)
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(3, weight=1)

        self._build_header()
        self._build_nav()
        self._build_content()
        self._build_log()
        self._build_status()

        i18n.subscribe(self._retranslate)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_header(self):
        header = ctk.CTkFrame(self.root, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 6))
        header.grid_columnconfigure(1, weight=1)

        logo = ctk.CTkLabel(header, text="P", font=("Segoe UI Black", 22),
                            text_color="#ffffff", width=46, height=46)
        img = grad_ctkimage(46, 46, GRAD_START, GRAD_END, radius=13)
        if img:
            logo.configure(image=img, compound="center")
            logo._grad = img
        logo.grid(row=0, column=0, rowspan=2, padx=(0, 14))

        ctk.CTkLabel(header, text=__app_name__, font=FONT_TITLE,
                     text_color=ACCENT_CYAN).grid(row=0, column=1, sticky="sw")
        self._tag = ctk.CTkLabel(header, text=_t("app.tagline", "PDF + PSD в одном окне"),
                                 font=FONT_TAG, text_color=TEXT_MUTED)
        self._tag.grid(row=1, column=1, sticky="nw")

        lang_box = ctk.CTkFrame(header, fg_color="transparent")
        lang_box.grid(row=0, column=2, rowspan=2, sticky="e")
        self._lang_lbl = ctk.CTkLabel(lang_box, text=_t("lang.label", "Язык:"),
                                      font=FONT, text_color=TEXT_SECONDARY)
        self._lang_lbl.pack(side="left", padx=(0, 8))
        self._lang = ctk.CTkOptionMenu(lang_box, values=["ru", "en"], command=self._on_lang,
                                       width=90, fg_color=BG_INPUT, button_color=ACCENT_CYAN,
                                       button_hover_color=ACCENT_CYAN_HOVER, corner_radius=8)
        self._lang.set(config.get("language", "ru"))
        self._lang.pack(side="left")

        GradientDivider(self.root, GRAD_START, GRAD_END, height=3).grid(
            row=1, column=0, sticky="ew", padx=18, pady=(2, 0))

    def _build_nav(self):
        self._tabs = {
            _t("tab.pdf", "PDF Tools"): "pdf",
            _t("tab.psd", "PSD Tools"): "psd",
            _t("tab.settings", "Настройки"): "settings",
            _t("tab.about", "О программе"): "about",
        }
        bar = ctk.CTkFrame(self.root, fg_color=BG_SIDEBAR, corner_radius=12)
        bar.grid(row=2, column=0, pady=(12, 10))
        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.pack(padx=6, pady=6)

        self._nav_btns, self._nav_imgs = {}, {}
        for label, key in self._tabs.items():
            gimg = grad_ctkimage(160, 38, GRAD_START, GRAD_END, radius=10)
            b = ctk.CTkButton(inner, text=label, width=160, height=38, corner_radius=10,
                              font=FONT_H, fg_color="transparent", hover_color=BG_INPUT,
                              text_color=TEXT_SECONDARY, border_width=0,
                              command=lambda l=label: self._select(l))
            b.pack(side="left", padx=4)
            self._nav_btns[key] = b
            self._nav_imgs[key] = gimg

    def _build_content(self):
        self._content = ctk.CTkFrame(self.root, fg_color="transparent")
        self._content.grid(row=3, column=0, sticky="nsew", padx=18)
        self._content.grid_columnconfigure(0, weight=1)
        self._content.grid_rowconfigure(0, weight=1)
        self._frames = {}

        def _log(msg, level="info"):
            self.log_panel.log(msg, level)
        self._log_fn = _log

    def _build_log(self):
        self.log_panel = LogPanel(self.root)
        self.log_panel.grid(row=4, column=0, sticky="ew", padx=18, pady=(10, 6))
        self._frames["pdf"] = PdfToolsFrameCTk(self._content, log=self._log_fn)
        self._frames["psd"] = PsdToolsFrameCTk(self._content, log=self._log_fn)
        self._frames["settings"] = SettingsFrame(self._content, on_theme_change=self._change_theme)
        self._frames["about"] = AboutFrame(self._content)
        for f in self._frames.values():
            f.grid(row=0, column=0, sticky="nsew")
        self._select(list(self._tabs.keys())[0])

    def _build_status(self):
        bar = ctk.CTkFrame(self.root, fg_color="transparent")
        bar.grid(row=5, column=0, sticky="ew", padx=20, pady=(0, 8))
        self._status = ctk.CTkLabel(bar, text=_t("status.ready", "Готово"),
                                    font=FONT, text_color=TEXT_MUTED)
        self._status.pack(side="left")

    def _select(self, label):
        key = self._tabs.get(label, "pdf")
        for k, b in self._nav_btns.items():
            if k == key:
                b.configure(image=self._nav_imgs[k], compound="center", text_color="#ffffff")
            else:
                b.configure(image=None, text_color=TEXT_SECONDARY)
        frame = self._frames.get(key)
        if frame:
            frame.tkraise()

    def _on_lang(self, value):
        config.set("language", value); i18n.set_language(value)

    def _change_theme(self, mode):
        apply_ctk_theme(self.root, mode=mode)

    def _retranslate(self):
        self._tag.configure(text=_t("app.tagline", "PDF + PSD в одном окне"))
        self._lang_lbl.configure(text=_t("lang.label", "Язык:"))
        self._status.configure(text=_t("status.ready", "Готово"))

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
