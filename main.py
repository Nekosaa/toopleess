"""Prizma Studio – application entry point."""
from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from core import __app_name__, __author__, __version__
from core.config import config
from core.i18n import i18n
from core.theme import apply_theme
from modules.pdf_tools_tab import PdfToolsFrame
from modules.psd_tools_tab import PsdToolsFrame


ASSETS_DIR = _HERE / "assets"


# ---------------------------------------------------------------------------
# Log panel – shared across tabs.
# ---------------------------------------------------------------------------
class LogPanel(ttk.Frame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=(8, 4))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        self._title_lbl = ttk.Label(header, text=i18n.t("log.title"),
                                    font=("Segoe UI", 10, "bold"))
        self._title_lbl.grid(row=0, column=0, sticky="w")

        self._clear_btn = ttk.Button(header, text=i18n.t("log.clear"),
                                     command=self.clear)
        self._clear_btn.grid(row=0, column=1, sticky="e")

        self._text = tk.Text(self, height=6, wrap="word", relief="flat",
                             borderwidth=0)
        self._text.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        self._text.configure(state="disabled")

        scroll = ttk.Scrollbar(self, orient="vertical", command=self._text.yview)
        scroll.grid(row=1, column=1, sticky="ns", pady=(4, 0))
        self._text.configure(yscrollcommand=scroll.set)

        i18n.subscribe(self._retranslate)

    def _retranslate(self) -> None:
        self._title_lbl.configure(text=i18n.t("log.title"))
        self._clear_btn.configure(text=i18n.t("log.clear"))

    def log(self, message: str, level: str = "info") -> None:
        prefix = {"info": "•", "warn": "!", "error": "×", "ok": "✓"}.get(level, "•")
        self._text.configure(state="normal")
        self._text.insert("end", f"{prefix} {message}\n")
        self._text.see("end")
        self._text.configure(state="disabled")

    def clear(self) -> None:
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(state="disabled")


# ---------------------------------------------------------------------------
# Settings tab.
# ---------------------------------------------------------------------------
class SettingsFrame(ttk.Frame):
    def __init__(self, master: tk.Misc, on_theme_change) -> None:
        super().__init__(master, padding=20)
        self._on_theme_change = on_theme_change

        self._lang_var = tk.StringVar(value=config.get("language"))
        self._theme_var = tk.StringVar(value=config.get("theme"))
        self._depth_var = tk.IntVar(value=int(config.get("smart_object_depth", 3)))
        self._pdf_dir_var = tk.StringVar(value=config.get("pdf_last_dir"))
        self._psd_in_var = tk.StringVar(value=config.get("psd_in_dir"))
        self._psd_out_var = tk.StringVar(value=config.get("psd_out_dir"))

        self._build()
        i18n.subscribe(self._retranslate)

    def _build(self) -> None:
        for col in range(3):
            self.columnconfigure(col, weight=(1 if col == 1 else 0))

        self._lbl_lang = ttk.Label(self, text=i18n.t("settings.language"),
                                   font=("Segoe UI", 10, "bold"))
        self._lbl_lang.grid(row=0, column=0, sticky="w", pady=(0, 4))
        self._lang_combo = ttk.Combobox(self, textvariable=self._lang_var,
                                        values=["ru", "en"], state="readonly", width=12)
        self._lang_combo.grid(row=0, column=1, sticky="w", pady=(0, 4))
        self._lang_combo.bind("<<ComboboxSelected>>", lambda _e: self._apply_lang())

        self._lbl_hint = ttk.Label(self, text=i18n.t("settings.restart"), foreground="#888")
        self._lbl_hint.grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 16))

        self._lbl_theme = ttk.Label(self, text=i18n.t("settings.theme"),
                                    font=("Segoe UI", 10, "bold"))
        self._lbl_theme.grid(row=2, column=0, sticky="w", pady=(0, 4))
        self._theme_combo = ttk.Combobox(self, textvariable=self._theme_var,
                                         values=["system", "light", "dark"],
                                         state="readonly", width=12)
        self._theme_combo.grid(row=2, column=1, sticky="w", pady=(0, 4))
        self._theme_combo.bind("<<ComboboxSelected>>", lambda _e: self._apply_theme())

        self._lbl_paths = ttk.Label(self, text=i18n.t("settings.paths"),
                                    font=("Segoe UI", 10, "bold"))
        self._lbl_paths.grid(row=3, column=0, sticky="w", pady=(16, 4))

        self._row_path("settings.pdf_dir", self._pdf_dir_var, 4, "pdf_last_dir")
        self._row_path("settings.psd_in",  self._psd_in_var,  5, "psd_in_dir")
        self._row_path("settings.psd_out", self._psd_out_var, 6, "psd_out_dir")

        self._lbl_depth = ttk.Label(self, text=i18n.t("settings.depth"),
                                    font=("Segoe UI", 10, "bold"))
        self._lbl_depth.grid(row=7, column=0, sticky="w", pady=(16, 4))
        depth_spin = ttk.Spinbox(self, from_=1, to=10, textvariable=self._depth_var,
                                 width=5, command=self._apply_depth)
        depth_spin.grid(row=7, column=1, sticky="w", pady=(16, 4))
        self._depth_var.trace_add("write", lambda *_: self._apply_depth())

    def _row_path(self, key: str, var: tk.StringVar, row: int, cfg_key: str) -> None:
        lbl = ttk.Label(self, text=i18n.t(key))
        lbl.grid(row=row, column=0, sticky="w", padx=(0, 12), pady=2)
        entry = ttk.Entry(self, textvariable=var)
        entry.grid(row=row, column=1, sticky="ew", pady=2)
        btn = ttk.Button(self, text=i18n.t("common.browse"),
                         command=lambda: self._pick_dir(var, cfg_key))
        btn.grid(row=row, column=2, sticky="w", padx=(8, 0), pady=2)
        var.trace_add("write", lambda *_: config.set(cfg_key, var.get()))
        setattr(self, f"_lbl_{cfg_key}", lbl)
        setattr(self, f"_btn_{cfg_key}", btn)

    def _pick_dir(self, var: tk.StringVar, cfg_key: str) -> None:
        chosen = filedialog.askdirectory(initialdir=var.get() or str(Path.home()))
        if chosen:
            var.set(chosen)
            config.set(cfg_key, chosen)

    def _apply_lang(self) -> None:
        lang = self._lang_var.get()
        config.set("language", lang)
        i18n.set_language(lang)

    def _apply_theme(self) -> None:
        mode = self._theme_var.get()
        config.set("theme", mode)
        self._on_theme_change(mode)

    def _apply_depth(self) -> None:
        try:
            config.set("smart_object_depth", int(self._depth_var.get()))
        except (tk.TclError, ValueError):
            pass

    def _retranslate(self) -> None:
        self._lbl_lang.configure(text=i18n.t("settings.language"))
        self._lbl_theme.configure(text=i18n.t("settings.theme"))
        self._lbl_paths.configure(text=i18n.t("settings.paths"))
        self._lbl_depth.configure(text=i18n.t("settings.depth"))
        self._lbl_hint.configure(text=i18n.t("settings.restart"))
        self._lbl_pdf_last_dir.configure(text=i18n.t("settings.pdf_dir"))
        self._lbl_psd_in_dir.configure(text=i18n.t("settings.psd_in"))
        self._lbl_psd_out_dir.configure(text=i18n.t("settings.psd_out"))
        for cfg_key in ("pdf_last_dir", "psd_in_dir", "psd_out_dir"):
            getattr(self, f"_btn_{cfg_key}").configure(text=i18n.t("common.browse"))


# ---------------------------------------------------------------------------
# About tab.
# ---------------------------------------------------------------------------
class AboutFrame(ttk.Frame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=32)
        self.columnconfigure(0, weight=1)

        self._title = ttk.Label(self, text=__app_name__,
                                font=("Segoe UI", 22, "bold"))
        self._title.grid(row=0, column=0, sticky="w")

        self._tagline = ttk.Label(self, text=i18n.t("app.tagline"),
                                  font=("Segoe UI", 11), foreground="#888")
        self._tagline.grid(row=1, column=0, sticky="w", pady=(2, 20))

        self._version_lbl = ttk.Label(
            self,
            text=f"{i18n.t('about.version')}: {__version__}",
            font=("Segoe UI", 10),
        )
        self._version_lbl.grid(row=2, column=0, sticky="w", pady=2)

        self._author_lbl = ttk.Label(
            self,
            text=f"{i18n.t('about.author')}: {__author__}",
            font=("Segoe UI", 10),
        )
        self._author_lbl.grid(row=3, column=0, sticky="w", pady=2)

        self._desc = ttk.Label(self, text=i18n.t("about.description"),
                               justify="left", wraplength=640)
        self._desc.grid(row=4, column=0, sticky="w", pady=(20, 10))

        self._tech_lbl = ttk.Label(
            self,
            text=f"{i18n.t('about.tech')}: Python · Tkinter · sv-ttk · PyMuPDF · Pillow · pywin32",
            foreground="#888",
        )
        self._tech_lbl.grid(row=5, column=0, sticky="w", pady=(20, 0))

        i18n.subscribe(self._retranslate)

    def _retranslate(self) -> None:
        self._tagline.configure(text=i18n.t("app.tagline"))
        self._version_lbl.configure(text=f"{i18n.t('about.version')}: {__version__}")
        self._author_lbl.configure(text=f"{i18n.t('about.author')}: {__author__}")
        self._desc.configure(text=i18n.t("about.description"))
        self._tech_lbl.configure(
            text=f"{i18n.t('about.tech')}: Python · Tkinter · sv-ttk · PyMuPDF · Pillow · pywin32"
        )


# ---------------------------------------------------------------------------
# Main window.
# ---------------------------------------------------------------------------
class MainApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        i18n.set_language(config.get("language", "ru"))

        root.title(f"{__app_name__} · v{__version__}")
        root.geometry(config.get("window_geometry", "1200x760"))
        root.minsize(1000, 640)

        icon_path = ASSETS_DIR / "icon.ico"
        if icon_path.exists():
            try:
                root.iconbitmap(default=str(icon_path))
            except tk.TclError:
                pass

        apply_theme(root, config.get("theme", "system"))

        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)

        self._build_top_bar()
        self._build_notebook()
        self._build_log()
        self._build_status_bar()

        i18n.subscribe(self._retranslate)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_top_bar(self) -> None:
        bar = ttk.Frame(self.root, padding=(16, 10))
        bar.grid(row=0, column=0, sticky="ew")
        bar.columnconfigure(1, weight=1)

        self._brand = ttk.Label(bar, text=f"◆  {__app_name__}",
                                font=("Segoe UI", 14, "bold"))
        self._brand.grid(row=0, column=0, sticky="w")

        self._tagline = ttk.Label(bar, text=i18n.t("app.tagline"),
                                  foreground="#888", font=("Segoe UI", 9))
        self._tagline.grid(row=1, column=0, sticky="w")

        right = ttk.Frame(bar)
        right.grid(row=0, column=2, rowspan=2, sticky="e")

        self._lang_lbl = ttk.Label(right, text=i18n.t("lang.label"))
        self._lang_lbl.pack(side="left", padx=(0, 6))

        self._lang_var = tk.StringVar(value=config.get("language", "ru"))
        self._lang_combo = ttk.Combobox(
            right, textvariable=self._lang_var,
            values=["ru", "en"], state="readonly", width=6,
        )
        self._lang_combo.pack(side="left")
        self._lang_combo.bind("<<ComboboxSelected>>", self._on_lang_change)

    def _build_notebook(self) -> None:
        self.notebook = ttk.Notebook(self.root)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))

        def _log(msg: str, level: str = "info") -> None:
            self.log_panel.log(msg, level)

        self.pdf_tab = PdfToolsFrame(self.notebook, log=_log)
        self.psd_tab = PsdToolsFrame(self.notebook, log=_log)
        self.settings_tab = SettingsFrame(self.notebook,
                                          on_theme_change=self._change_theme)
        self.about_tab = AboutFrame(self.notebook)

        self.notebook.add(self.pdf_tab, text=i18n.t("tab.pdf"))
        self.notebook.add(self.psd_tab, text=i18n.t("tab.psd"))
        self.notebook.add(self.settings_tab, text=i18n.t("tab.settings"))
        self.notebook.add(self.about_tab, text=i18n.t("tab.about"))

    def _build_log(self) -> None:
        self.log_panel = LogPanel(self.root)
        self.log_panel.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 4))

    def _build_status_bar(self) -> None:
        self._status_var = tk.StringVar(value=i18n.t("status.ready"))
        bar = ttk.Frame(self.root, padding=(12, 4))
        bar.grid(row=3, column=0, sticky="ew")
        bar.columnconfigure(0, weight=1)
        self._status_lbl = ttk.Label(bar, textvariable=self._status_var,
                                     foreground="#888")
        self._status_lbl.grid(row=0, column=0, sticky="w")

    def _on_lang_change(self, _event) -> None:
        lang = self._lang_var.get()
        config.set("language", lang)
        i18n.set_language(lang)

    def _change_theme(self, mode: str) -> None:
        apply_theme(self.root, mode)

    def _retranslate(self) -> None:
        self._tagline.configure(text=i18n.t("app.tagline"))
        self._lang_lbl.configure(text=i18n.t("lang.label"))
        self._status_var.set(i18n.t("status.ready"))
        self.notebook.tab(self.pdf_tab,      text=i18n.t("tab.pdf"))
        self.notebook.tab(self.psd_tab,      text=i18n.t("tab.psd"))
        self.notebook.tab(self.settings_tab, text=i18n.t("tab.settings"))
        self.notebook.tab(self.about_tab,    text=i18n.t("tab.about"))

    def _on_close(self) -> None:
        try:
            config.set("window_geometry", self.root.geometry())
        finally:
            self.root.destroy()


def main() -> None:
    root = tk.Tk()
    MainApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
