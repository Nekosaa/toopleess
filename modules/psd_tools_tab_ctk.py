"""PSD Tools Tab - профессиональный CustomTkinter UI (логика взята из psd_tools_tab)."""
from __future__ import annotations

import customtkinter as ctk
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

from core.config import config
from core.i18n import i18n
from core.ctk_theme import (
    BG_CARD, BG_SIDEBAR, BG_INPUT, BG_MAIN,
    ACCENT_CYAN, ACCENT_CYAN_HOVER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    BORDER, ERROR,
)
from modules.psd_tools_tab import PsdToolsFrame  # источник логики

FONT_BTN = ("Segoe UI", 12)
FONT_LBL = ("Segoe UI", 12, "bold")
FONT_SECTION = ("Segoe UI", 11, "bold")
FONT_HINT = ("Segoe UI", 11)


class PsdToolsFrameCTk(ctk.CTkFrame):
    def __init__(self, master, log) -> None:
        super().__init__(master, fg_color="transparent")
        self._log = log
        self._ps = None
        self._doc = None
        self._psd_path = None
        self._layers_index = []
        self._so_frames = {}
        self._small_source_ack = False

        self._mode_var = tk.StringVar(value=config.get("psd_mode", "fill"))
        self._no_upscale_var = tk.BooleanVar(value=bool(config.get("psd_no_upscale", False)))
        self._clip_bounds_var = tk.BooleanVar(value=bool(config.get("psd_clip_to_bounds", True)))
        self._inherit_meta_var = tk.BooleanVar(value=bool(config.get("psd_inherit_metadata", True)))
        self._in_var = tk.StringVar(value=config.get("psd_in_dir") or "")
        self._out_var = tk.StringVar(value=config.get("psd_out_dir") or "")

        self._mode_var.trace_add("write", lambda *_: config.set("psd_mode", self._mode_var.get()))
        self._no_upscale_var.trace_add("write", lambda *_: config.set("psd_no_upscale", bool(self._no_upscale_var.get())))
        self._clip_bounds_var.trace_add("write", lambda *_: config.set("psd_clip_to_bounds", bool(self._clip_bounds_var.get())))
        self._inherit_meta_var.trace_add("write", lambda *_: config.set("psd_inherit_metadata", bool(self._inherit_meta_var.get())))
        self._in_var.trace_add("write", lambda *_: config.set("psd_in_dir", self._in_var.get()))
        self._out_var.trace_add("write", lambda *_: config.set("psd_out_dir", self._out_var.get()))

        self._build()
        i18n.subscribe(self._retranslate)

    # ---- фабрики кнопок -----------------------------------------------
    def _btn_primary(self, parent, text, command, width=0):
        return ctk.CTkButton(parent, text=text, command=command, font=FONT_BTN,
                             fg_color=ACCENT_CYAN, hover_color=ACCENT_CYAN_HOVER,
                             text_color="#ffffff", text_color_disabled=TEXT_MUTED,
                             corner_radius=8, height=34, width=width or 150)

    def _btn_ghost(self, parent, text, command, width=0):
        return ctk.CTkButton(parent, text=text, command=command, font=FONT_BTN,
                             fg_color="transparent", hover_color=BG_INPUT,
                             text_color=TEXT_PRIMARY, text_color_disabled=TEXT_MUTED,
                             border_width=1, border_color=BORDER,
                             corner_radius=8, height=34, width=width or 120)

    def _build(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- Тулбар (2 ряда) ---
        toolbar = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12,
                               border_width=1, border_color=BORDER)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        self._btn_open = self._btn_primary(toolbar, i18n.t("psd.open"), self.open_psd, width=150)
        self._btn_scan = self._btn_ghost(toolbar, i18n.t("psd.scan"), self.scan_layers, width=150)
        self._btn_unlck = self._btn_ghost(toolbar, i18n.t("psd.unlock"), self.unlock_all, width=180)
        self._btn_repl = self._btn_ghost(toolbar, i18n.t("psd.replace"), self.replace_in_selected, width=210)
        for i, b in enumerate((self._btn_open, self._btn_scan, self._btn_unlck, self._btn_repl)):
            b.grid(row=0, column=i, padx=(10 if i == 0 else 6, 6), pady=(10, 5), sticky="w")

        self._btn_auto = self._btn_ghost(toolbar, "Авто фото", self.auto_replace_photo, width=120)
        self._btn_picker = self._btn_ghost(toolbar, "Выбор SO", self.open_so_picker, width=120)
        self._btn_all_so = self._btn_ghost(toolbar, "Во все SO", self.replace_all_so_dialog, width=120)
        self._btn_csv = self._btn_ghost(toolbar, "Batch CSV", self.batch_csv_replace, width=120)
        for i, b in enumerate((self._btn_auto, self._btn_picker, self._btn_all_so, self._btn_csv)):
            b.grid(row=1, column=i, padx=(10 if i == 0 else 6, 6), pady=(0, 10), sticky="w")

        # --- Левая панель: список слоёв ---
        left = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12,
                            border_width=1, border_color=BORDER, width=280)
        left.grid(row=1, column=0, sticky="ns", padx=(0, 12))
        left.grid_propagate(False)
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        self._lbl_layers = ctk.CTkLabel(left, text=i18n.t("psd.section.layers").upper(),
                                        font=FONT_SECTION, text_color=TEXT_SECONDARY)
        self._lbl_layers.grid(row=0, column=0, sticky="w", padx=16, pady=(14, 6))

        list_wrap = ctk.CTkFrame(left, fg_color=BG_INPUT, corner_radius=8,
                                 border_width=1, border_color=BORDER)
        list_wrap.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        list_wrap.grid_rowconfigure(0, weight=1)
        list_wrap.grid_columnconfigure(0, weight=1)

        self._listbox = tk.Listbox(list_wrap, activestyle="none", relief="flat",
                                   bg=BG_INPUT, fg=TEXT_PRIMARY,
                                   selectbackground=ACCENT_CYAN, selectforeground="#ffffff",
                                   highlightthickness=0, borderwidth=0,
                                   font=("Consolas", 10))
        self._listbox.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        sb = ctk.CTkScrollbar(list_wrap, command=self._listbox.yview,
                              button_color=BORDER, button_hover_color=ACCENT_CYAN,
                              fg_color="transparent", width=12)
        sb.grid(row=0, column=1, sticky="ns", padx=(0, 4), pady=6)
        self._listbox.configure(yscrollcommand=sb.set)

        # --- Правая панель: действия ---
        right = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12,
                             border_width=1, border_color=BORDER)
        right.grid(row=1, column=1, sticky="nsew")
        right.grid_columnconfigure(1, weight=1)

        self._lbl_actions = ctk.CTkLabel(right, text=i18n.t("psd.section.actions").upper(),
                                         font=FONT_SECTION, text_color=TEXT_SECONDARY)
        self._lbl_actions.grid(row=0, column=0, columnspan=4, sticky="w", padx=18, pady=(16, 10))

        self._lbl_mode = ctk.CTkLabel(right, text=i18n.t("psd.mode"), font=FONT_BTN,
                                      text_color=TEXT_PRIMARY)
        self._lbl_mode.grid(row=1, column=0, sticky="w", padx=18, pady=4)

        modes = ctk.CTkFrame(right, fg_color="transparent")
        modes.grid(row=1, column=1, columnspan=3, sticky="w", padx=6, pady=4)
        self._rb_fit = ctk.CTkRadioButton(modes, text=i18n.t("psd.mode.fit"),
                                          variable=self._mode_var, value="fit",
                                          fg_color=ACCENT_CYAN, hover_color=ACCENT_CYAN_HOVER,
                                          text_color=TEXT_PRIMARY, font=FONT_BTN)
        self._rb_fill = ctk.CTkRadioButton(modes, text=i18n.t("psd.mode.fill"),
                                           variable=self._mode_var, value="fill",
                                           fg_color=ACCENT_CYAN, hover_color=ACCENT_CYAN_HOVER,
                                           text_color=TEXT_PRIMARY, font=FONT_BTN)
        self._rb_orig = ctk.CTkRadioButton(modes, text=i18n.t("psd.mode.original"),
                                           variable=self._mode_var, value="original",
                                           fg_color=ACCENT_CYAN, hover_color=ACCENT_CYAN_HOVER,
                                           text_color=TEXT_PRIMARY, font=FONT_BTN)
        self._rb_fit.pack(side="left", padx=(0, 16))
        self._rb_fill.pack(side="left", padx=(0, 16))
        self._rb_orig.pack(side="left")

        self._lbl_mode_hint = ctk.CTkLabel(right, text=i18n.t("psd.mode.hint"),
                                           text_color=TEXT_MUTED, font=FONT_HINT,
                                           wraplength=560, justify="left")
        self._lbl_mode_hint.grid(row=2, column=0, columnspan=4, sticky="w", padx=18, pady=(2, 8))

        self._cb_no_upscale = ctk.CTkCheckBox(right, text=i18n.t("psd.no.upscale"),
                                              variable=self._no_upscale_var, onvalue=True, offvalue=False,
                                              fg_color=ACCENT_CYAN, hover_color=ACCENT_CYAN_HOVER,
                                              text_color=TEXT_PRIMARY, font=FONT_BTN)
        self._cb_no_upscale.grid(row=3, column=0, columnspan=4, sticky="w", padx=18, pady=3)
        self._cb_clip_bounds = ctk.CTkCheckBox(right, text=i18n.t("psd.clip.bounds"),
                                               variable=self._clip_bounds_var, onvalue=True, offvalue=False,
                                               fg_color=ACCENT_CYAN, hover_color=ACCENT_CYAN_HOVER,
                                               text_color=TEXT_PRIMARY, font=FONT_BTN)
        self._cb_clip_bounds.grid(row=4, column=0, columnspan=4, sticky="w", padx=18, pady=3)
        self._cb_inherit_meta = ctk.CTkCheckBox(right, text=i18n.t("psd.inherit.metadata"),
                                                variable=self._inherit_meta_var, onvalue=True, offvalue=False,
                                                fg_color=ACCENT_CYAN, hover_color=ACCENT_CYAN_HOVER,
                                                text_color=TEXT_PRIMARY, font=FONT_BTN)
        self._cb_inherit_meta.grid(row=5, column=0, columnspan=4, sticky="w", padx=18, pady=3)

        ctk.CTkFrame(right, fg_color=BORDER, height=1).grid(
            row=6, column=0, columnspan=4, sticky="ew", padx=18, pady=14)

        self._lbl_batch = ctk.CTkLabel(right, text=i18n.t("psd.section.batch").upper(),
                                       font=FONT_SECTION, text_color=TEXT_SECONDARY)
        self._lbl_batch.grid(row=7, column=0, columnspan=4, sticky="w", padx=18, pady=(0, 10))

        self._lbl_in = ctk.CTkLabel(right, text=i18n.t("psd.in.folder"), font=FONT_BTN,
                                    text_color=TEXT_PRIMARY)
        self._lbl_in.grid(row=8, column=0, sticky="w", padx=18, pady=4)
        ctk.CTkEntry(right, textvariable=self._in_var, fg_color=BG_INPUT, border_color=BORDER,
                     text_color=TEXT_PRIMARY, corner_radius=8, height=34).grid(
            row=8, column=1, columnspan=2, sticky="ew", padx=6, pady=4)
        self._btn_in = self._btn_ghost(right, i18n.t("common.browse"),
                                       lambda: self._pick(self._in_var, "psd_in_dir"), width=100)
        self._btn_in.grid(row=8, column=3, sticky="w", padx=(6, 18), pady=4)

        self._lbl_out = ctk.CTkLabel(right, text=i18n.t("psd.out.folder"), font=FONT_BTN,
                                     text_color=TEXT_PRIMARY)
        self._lbl_out.grid(row=9, column=0, sticky="w", padx=18, pady=4)
        ctk.CTkEntry(right, textvariable=self._out_var, fg_color=BG_INPUT, border_color=BORDER,
                     text_color=TEXT_PRIMARY, corner_radius=8, height=34).grid(
            row=9, column=1, columnspan=2, sticky="ew", padx=6, pady=4)
        self._btn_out = self._btn_ghost(right, i18n.t("common.browse"),
                                        lambda: self._pick(self._out_var, "psd_out_dir"), width=100)
        self._btn_out.grid(row=9, column=3, sticky="w", padx=(6, 18), pady=4)

        self._btn_batch = self._btn_primary(right, i18n.t("psd.batch"), self.batch_replace)
        self._btn_batch.grid(row=10, column=0, columnspan=4, sticky="ew", padx=18, pady=(14, 16))

        self._warn = ctk.CTkLabel(self, text="", text_color=ERROR, font=FONT_BTN)
        self._warn.grid(row=2, column=0, columnspan=2, sticky="w", padx=4, pady=(8, 0))

    def _pick(self, var, cfg_key) -> None:
        chosen = filedialog.askdirectory(initialdir=var.get() or str(Path.home()))
        if chosen:
            var.set(chosen)
            config.set(cfg_key, chosen)

    def _retranslate(self) -> None:
        self._btn_open.configure(text=i18n.t("psd.open"))
        self._btn_scan.configure(text=i18n.t("psd.scan"))
        self._btn_unlck.configure(text=i18n.t("psd.unlock"))
        self._btn_repl.configure(text=i18n.t("psd.replace"))
        self._btn_batch.configure(text=i18n.t("psd.batch"))
        self._btn_in.configure(text=i18n.t("common.browse"))
        self._btn_out.configure(text=i18n.t("common.browse"))
        self._rb_fit.configure(text=i18n.t("psd.mode.fit"))
        self._rb_fill.configure(text=i18n.t("psd.mode.fill"))
        self._rb_orig.configure(text=i18n.t("psd.mode.original"))
        self._cb_no_upscale.configure(text=i18n.t("psd.no.upscale"))
        self._cb_clip_bounds.configure(text=i18n.t("psd.clip.bounds"))
        self._cb_inherit_meta.configure(text=i18n.t("psd.inherit.metadata"))
        self._lbl_layers.configure(text=i18n.t("psd.section.layers").upper())
        self._lbl_actions.configure(text=i18n.t("psd.section.actions").upper())
        self._lbl_batch.configure(text=i18n.t("psd.section.batch").upper())
        self._lbl_mode.configure(text=i18n.t("psd.mode"))
        self._lbl_mode_hint.configure(text=i18n.t("psd.mode.hint"))
        self._lbl_in.configure(text=i18n.t("psd.in.folder"))
        self._lbl_out.configure(text=i18n.t("psd.out.folder"))
        if self._ps and not self._ps.available:
            self._warn.configure(text=f"{i18n.t('psd.no.photoshop')} ({self._ps.error()})")


# --- переиспользуем ВСЮ логику Photoshop из PsdToolsFrame ---
_OVERRIDDEN = {"__init__", "_build", "_retranslate", "_pick",
               "__dict__", "__weakref__", "__doc__", "__module__"}
for _name, _attr in vars(PsdToolsFrame).items():
    if _name in _OVERRIDDEN:
        continue
    if _name not in PsdToolsFrameCTk.__dict__:
        setattr(PsdToolsFrameCTk, _name, _attr)

__all__ = ["PsdToolsFrameCTk"]
