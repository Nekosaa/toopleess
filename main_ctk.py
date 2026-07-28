"""Prizma Studio – Modern CustomTkinter UI with bold purple-cyan theme."""
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
    BG_GRADIENT_START, BG_CARD, ACCENT_CYAN, ACCENT_PURPLE,
    TEXT_PRIMARY, TEXT_SECONDARY, NEON_GLOW, apply_ctk_theme
)

# Import modernized tabs (will create these)
from modules.pdf_tools_tab_ctk import PdfToolsFrameCTk
from modules.psd_tools_tab_ctk import PsdToolsFrameCTk


ASSETS_DIR = _HERE / "assets"


# ===========================================================================
# Modern Log Panel with Neon Accents
# ===========================================================================
class LogPanelCTk(ctk.CTkFrame):
    def __init__(self, master: ctk.CTk | ctk.CTkFrame) -> None:
        super().__init__(
            master,
            fg_color=BG_CARD,
            corner_radius=16,
            border_width=1,
            border_color=NEON_GLOW
        )
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header with glow effect
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        header.grid_columnconfigure(0, weight=1)

        self._title_lbl = ctk.CTkLabel(
            header,
            text=f"✨ {i18n.t('log.title')}",
            font=("Segoe UI", 14, "bold"),
            text_color=ACCENT_CYAN
        )
        self._title_lbl.grid(row=0, column=0, sticky="w")

        self._clear_btn = ctk.CTkButton(
            header,
            text=i18n.t("log.clear"),
            command=self.clear,
            width=100,
            height=28,
            corner_radius=8,
            fg_color=ACCENT_PURPLE,
            hover_color="#7c3aed"
        )
        self._clear_btn.grid(row=0, column=1, sticky="e")

        # Textbox with custom styling
        self._text = ctk.CTkTextbox(
            self,
            height=120,
            wrap="word",
            corner_radius=12,
            border_width=1,
            border_color=ACCENT_CYAN,
            fg_color="#0f0e1a",
            text_color=TEXT_PRIMARY,
            font=("Consolas", 10)
        )
        self._text.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self._text.configure(state="disabled")

        i18n.subscribe(self._retranslate)

    def _retranslate(self) -> None:
        self._title_lbl.configure(text=f"✨ {i18n.t('log.title')}")
        self._clear_btn.configure(text=i18n.t("log.clear"))

    def log(self, message: str, level: str = "info") -> None:
        # Color-coded icons
        icons = {
            "info": ("💠", ACCENT_CYAN),
            "warn": ("⚠️", "#f59e0b"),
            "error": ("❌", "#ef4444"),
            "ok": ("✅", "#10b981")
        }
        icon, color = icons.get(level, ("•", TEXT_PRIMARY))
        
        self._text.configure(state="normal")
        self._text.insert("end", f"{icon} {message}\n")
        self._text.see("end")
        self._text.configure(state="disabled")

    def clear(self) -> None:
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(state="disabled")


# ===========================================================================
# Modern Settings Frame
# ===========================================================================
class SettingsFrameCTk(ctk.CTkFrame):
    def __init__(self, master: ctk.CTkFrame, on_theme_change) -> None:
        super().__init__(master, fg_color="transparent")
        self._on_theme_change = on_theme_change

        self._lang_var = ctk.StringVar(value=config.get("language"))
        self._theme_var = ctk.StringVar(value=config.get("theme"))
        self._depth_var = ctk.IntVar(value=int(config.get("smart_object_depth", 3)))
        self._pdf_dir_var = ctk.StringVar(value=config.get("pdf_last_dir"))
        self._psd_in_var = ctk.StringVar(value=config.get("psd_in_dir"))
        self._psd_out_var = ctk.StringVar(value=config.get("psd_out_dir"))

        self._build()
        i18n.subscribe(self._retranslate)

    def _build(self) -> None:
        # Container with padding
        container = ctk.CTkFrame(
            self,
            fg_color=BG_CARD,
            corner_radius=16,
            border_width=1,
            border_color=NEON_GLOW
        )
        container.pack(fill="both", expand=True, padx=20, pady=20)
        container.grid_columnconfigure(1, weight=1)

        row = 0

        # Language section
        self._lbl_lang = ctk.CTkLabel(
            container,
            text=f"🌐 {i18n.t('settings.language')}",
            font=("Segoe UI", 14, "bold"),
            text_color=ACCENT_CYAN
        )
        self._lbl_lang.grid(row=row, column=0, sticky="w", padx=20, pady=(20, 8))
        
        self._lang_combo = ctk.CTkComboBox(
            container,
            variable=self._lang_var,
            values=["ru", "en"],
            state="readonly",
            width=150,
            corner_radius=8,
            command=lambda _: self._apply_lang()
        )
        self._lang_combo.grid(row=row, column=1, sticky="w", padx=20, pady=(20, 8))
        row += 1

        # Theme section
        self._lbl_theme = ctk.CTkLabel(
            container,
            text=f"🎨 {i18n.t('settings.theme')}",
            font=("Segoe UI", 14, "bold"),
            text_color=ACCENT_PURPLE
        )
        self._lbl_theme.grid(row=row, column=0, sticky="w", padx=20, pady=(16, 8))
        
        self._theme_combo = ctk.CTkComboBox(
            container,
            variable=self._theme_var,
            values=["system", "light", "dark"],
            state="readonly",
            width=150,
            corner_radius=8,
            command=lambda _: self._apply_theme()
        )
        self._theme_combo.grid(row=row, column=1, sticky="w", padx=20, pady=(16, 8))
        row += 1

        # Paths section
        ctk.CTkLabel(
            container,
            text="",
            height=1
        ).grid(row=row, column=0, pady=10)
        row += 1

        self._lbl_paths = ctk.CTkLabel(
            container,
            text=f"📁 {i18n.t('settings.paths')}",
            font=("Segoe UI", 14, "bold"),
            text_color=ACCENT_CYAN
        )
        self._lbl_paths.grid(row=row, column=0, columnspan=3, sticky="w", padx=20, pady=(8, 12))
        row += 1

        # Path rows
        self._row_path(container, "settings.pdf_dir", self._pdf_dir_var, row, "pdf_last_dir")
        row += 1
        self._row_path(container, "settings.psd_in", self._psd_in_var, row, "psd_in_dir")
        row += 1
        self._row_path(container, "settings.psd_out", self._psd_out_var, row, "psd_out_dir")
        row += 1

        # Depth setting
        ctk.CTkLabel(
            container,
            text="",
            height=1
        ).grid(row=row, column=0, pady=10)
        row += 1

        self._lbl_depth = ctk.CTkLabel(
            container,
            text=f"🔢 {i18n.t('settings.depth')}",
            font=("Segoe UI", 14, "bold"),
            text_color=ACCENT_PURPLE
        )
        self._lbl_depth.grid(row=row, column=0, sticky="w", padx=20, pady=(8, 8))
        
        depth_entry = ctk.CTkEntry(
            container,
            textvariable=self._depth_var,
            width=80,
            corner_radius=8
        )
        depth_entry.grid(row=row, column=1, sticky="w", padx=20, pady=(8, 8))
        self._depth_var.trace_add("write", lambda *_: self._apply_depth())

    def _row_path(self, parent, key: str, var: ctk.StringVar, row: int, cfg_key: str) -> None:
        lbl = ctk.CTkLabel(parent, text=i18n.t(key), text_color=TEXT_SECONDARY)
        lbl.grid(row=row, column=0, sticky="w", padx=20, pady=6)
        
        entry = ctk.CTkEntry(parent, textvariable=var, corner_radius=8)
        entry.grid(row=row, column=1, sticky="ew", padx=20, pady=6)
        
        btn = ctk.CTkButton(
            parent,
            text=i18n.t("common.browse"),
            command=lambda: self._pick_dir(var, cfg_key),
            width=100,
            corner_radius=8,
            fg_color=ACCENT_PURPLE
        )
        btn.grid(row=row, column=2, sticky="w", padx=(8, 20), pady=6)
        var.trace_add("write", lambda *_: config.set(cfg_key, var.get()))
        
        setattr(self, f"_lbl_{cfg_key}", lbl)
        setattr(self, f"_btn_{cfg_key}", btn)

    def _pick_dir(self, var: ctk.StringVar, cfg_key: str) -> None:
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
        except (ValueError, Exception):
            pass

    def _retranslate(self) -> None:
        self._lbl_lang.configure(text=f"🌐 {i18n.t('settings.language')}")
        self._lbl_theme.configure(text=f"🎨 {i18n.t('settings.theme')}")
        self._lbl_paths.configure(text=f"📁 {i18n.t('settings.paths')}")
        self._lbl_depth.configure(text=f"🔢 {i18n.t('settings.depth')}")
        
        for cfg_key in ("pdf_last_dir", "psd_in_dir", "psd_out_dir"):
            getattr(self, f"_btn_{cfg_key}").configure(text=i18n.t("common.browse"))


# ===========================================================================
# Modern About Frame
# ===========================================================================
class AboutFrameCTk(ctk.CTkFrame):
    def __init__(self, master: ctk.CTkFrame) -> None:
        super().__init__(master, fg_color="transparent")
        
        container = ctk.CTkFrame(
            self,
            fg_color=BG_CARD,
            corner_radius=16,
            border_width=1,
            border_color=NEON_GLOW
        )
        container.pack(fill="both", expand=True, padx=32, pady=32)
        container.grid_columnconfigure(0, weight=1)

        # Title with gradient effect (simulated)
        self._title = ctk.CTkLabel(
            container,
            text=f"◆ {__app_name__}",
            font=("Segoe UI", 32, "bold"),
            text_color=ACCENT_CYAN
        )
        self._title.grid(row=0, column=0, sticky="w", padx=32, pady=(32, 4))

        self._tagline = ctk.CTkLabel(
            container,
            text=i18n.t("app.tagline"),
            font=("Segoe UI", 14),
            text_color=TEXT_SECONDARY
        )
        self._tagline.grid(row=1, column=0, sticky="w", padx=32, pady=(4, 24))

        # Info section
        self._version_lbl = ctk.CTkLabel(
            container,
            text=f"🔖 {i18n.t('about.version')}: {__version__}",
            font=("Segoe UI", 12),
            text_color=TEXT_PRIMARY
        )
        self._version_lbl.grid(row=2, column=0, sticky="w", padx=32, pady=4)

        self._author_lbl = ctk.CTkLabel(
            container,
            text=f"👤 {i18n.t('about.author')}: {__author__}",
            font=("Segoe UI", 12),
            text_color=TEXT_PRIMARY
        )
        self._author_lbl.grid(row=3, column=0, sticky="w", padx=32, pady=4)

        # Description
        self._desc = ctk.CTkLabel(
            container,
            text=i18n.t("about.description"),
            font=("Segoe UI", 11),
            text_color=TEXT_SECONDARY,
            justify="left",
            wraplength=640
        )
        self._desc.grid(row=4, column=0, sticky="w", padx=32, pady=(24, 16))

        # Tech stack
        self._tech_lbl = ctk.CTkLabel(
            container,
            text=f"⚙️ {i18n.t('about.tech')}: Python · CustomTkinter · PyMuPDF · Pillow · pywin32",
            font=("Segoe UI", 10),
            text_color=ACCENT_PURPLE
        )
        self._tech_lbl.grid(row=5, column=0, sticky="w", padx=32, pady=(16, 32))

        i18n.subscribe(self._retranslate)

    def _retranslate(self) -> None:
        self._tagline.configure(text=i18n.t("app.tagline"))
        self._version_lbl.configure(text=f"🔖 {i18n.t('about.version')}: {__version__}")
        self._author_lbl.configure(text=f"👤 {i18n.t('about.author')}: {__author__}")
        self._desc.configure(text=i18n.t("about.description"))
        self._tech_lbl.configure(
            text=f"⚙️ {i18n.t('about.tech')}: Python · CustomTkinter · PyMuPDF · Pillow · pywin32"
        )


# ===========================================================================
# Main Application Window
# ===========================================================================
class MainAppCTk:
    def __init__(self, root: ctk.CTk) -> None:
        self.root = root
        i18n.set_language(config.get("language", "ru"))

        # Apply custom theme
        apply_ctk_theme()

        root.title(f"{__app_name__} · v{__version__}")
        root.geometry(config.get("window_geometry", "1280x820"))
        root.minsize(1100, 700)

        # Set icon
        icon_path = ASSETS_DIR / "icon.ico"
        if icon_path.exists():
            try:
                root.iconbitmap(default=str(icon_path))
            except Exception:
                pass

        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(1, weight=1)

        self._build_top_bar()
        self._build_tabview()
        self._build_log()
        self._build_status_bar()

        i18n.subscribe(self._retranslate)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_top_bar(self) -> None:
        """Modern gradient-style top bar."""
        bar = ctk.CTkFrame(
            self.root,
            fg_color=BG_CARD,
            corner_radius=0,
            border_width=0,
            height=80
        )
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_columnconfigure(1, weight=1)
        bar.grid_propagate(False)

        # Brand with glow effect
        self._brand = ctk.CTkLabel(
            bar,
            text=f"◆  {__app_name__}",
            font=("Segoe UI", 20, "bold"),
            text_color=ACCENT_CYAN
        )
        self._brand.grid(row=0, column=0, sticky="w", padx=24, pady=(16, 4))

        self._tagline = ctk.CTkLabel(
            bar,
            text=i18n.t("app.tagline"),
            font=("Segoe UI", 11),
            text_color=TEXT_SECONDARY
        )
        self._tagline.grid(row=1, column=0, sticky="w", padx=24, pady=(0, 16))

        # Language selector
        right = ctk.CTkFrame(bar, fg_color="transparent")
        right.grid(row=0, column=2, rowspan=2, sticky="e", padx=24)

        self._lang_lbl = ctk.CTkLabel(
            right,
            text=f"🌐 {i18n.t('lang.label')}",
            text_color=TEXT_SECONDARY
        )
        self._lang_lbl.pack(side="left", padx=(0, 8))

        self._lang_var = ctk.StringVar(value=config.get("language", "ru"))
        self._lang_combo = ctk.CTkComboBox(
            right,
            variable=self._lang_var,
            values=["ru", "en"],
            state="readonly",
            width=100,
            corner_radius=8,
            command=self._on_lang_change
        )
        self._lang_combo.pack(side="left")

    def _build_tabview(self) -> None:
        """Modern tabview with glow effects."""
        # Create main container
        self.tab_container = ctk.CTkFrame(self.root, fg_color="transparent")
        self.tab_container.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 12))
        self.tab_container.grid_columnconfigure(0, weight=1)
        self.tab_container.grid_rowconfigure(0, weight=1)

        # Create tabview
        self.tabview = ctk.CTkTabview(
            self.tab_container,
            corner_radius=16,
            border_width=1,
            border_color=NEON_GLOW,
            fg_color=BG_CARD,
            segmented_button_fg_color=BG_GRADIENT_START,
            segmented_button_selected_color=ACCENT_CYAN,
            segmented_button_selected_hover_color="#0891b2",
            segmented_button_unselected_color=BG_CARD,
            segmented_button_unselected_hover_color=ACCENT_PURPLE
        )
        self.tabview.grid(row=0, column=0, sticky="nsew")

        # Add tabs
        self.tabview.add(i18n.t("tab.pdf"))
        self.tabview.add(i18n.t("tab.psd"))
        self.tabview.add(i18n.t("tab.settings"))
        self.tabview.add(i18n.t("tab.about"))

        # Log callback
        def _log(msg: str, level: str = "info") -> None:
            self.log_panel.log(msg, level)

        # Create tab content
        self.pdf_tab = PdfToolsFrameCTk(self.tabview.tab(i18n.t("tab.pdf")), log=_log)
        self.psd_tab = PsdToolsFrameCTk(self.tabview.tab(i18n.t("tab.psd")), log=_log)
        self.settings_tab = SettingsFrameCTk(
            self.tabview.tab(i18n.t("tab.settings")),
            on_theme_change=self._change_theme
        )
        self.about_tab = AboutFrameCTk(self.tabview.tab(i18n.t("tab.about")))

        # Pack tab contents
        self.pdf_tab.pack(fill="both", expand=True)
        self.psd_tab.pack(fill="both", expand=True)
        self.settings_tab.pack(fill="both", expand=True)
        self.about_tab.pack(fill="both", expand=True)

    def _build_log(self) -> None:
        """Modern log panel with neon styling."""
        self.log_panel = LogPanelCTk(self.root)
        self.log_panel.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 8))

    def _build_status_bar(self) -> None:
        """Modern status bar."""
        self._status_var = ctk.StringVar(value=i18n.t("status.ready"))
        bar = ctk.CTkFrame(
            self.root,
            fg_color=BG_CARD,
            corner_radius=0,
            height=32
        )
        bar.grid(row=3, column=0, sticky="ew")
        bar.grid_columnconfigure(0, weight=1)
        bar.grid_propagate(False)

        self._status_lbl = ctk.CTkLabel(
            bar,
            textvariable=self._status_var,
            text_color=TEXT_SECONDARY,
            font=("Segoe UI", 10)
        )
        self._status_lbl.grid(row=0, column=0, sticky="w", padx=16)

    def _on_lang_change(self, _event=None) -> None:
        lang = self._lang_var.get()
        config.set("language", lang)
        i18n.set_language(lang)

    def _change_theme(self, mode: str) -> None:
        # CustomTkinter handles theme changes
        if mode == "dark":
            ctk.set_appearance_mode("dark")
        elif mode == "light":
            ctk.set_appearance_mode("light")
        else:
            ctk.set_appearance_mode("system")

    def _retranslate(self) -> None:
        self._tagline.configure(text=i18n.t("app.tagline"))
        self._lang_lbl.configure(text=f"🌐 {i18n.t('lang.label')}")
        self._status_var.set(i18n.t("status.ready"))
        
        # Update tab names (note: CTkTabview doesn't support dynamic renaming easily)
        # Would need to recreate tabs - skipping for now

    def _on_close(self) -> None:
        try:
            config.set("window_geometry", self.root.geometry())
        finally:
            self.root.destroy()


def main() -> None:
    # Set CustomTkinter appearance
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    
    root = ctk.CTk()
    root.configure(fg_color=BG_GRADIENT_START)
    
    MainAppCTk(root)
    root.mainloop()


if __name__ == "__main__":
    main()
