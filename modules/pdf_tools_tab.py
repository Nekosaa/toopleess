"""PDF Tools Tab – CustomTkinter modernized version."""
from __future__ import annotations

import customtkinter as ctk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog
from typing import Callable, Optional

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None  # type: ignore

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None  # type: ignore
    ImageTk = None  # type: ignore

from core.config import config
from core.i18n import i18n
from core.ctk_theme import (
    BG_CARD, ACCENT_CYAN, ACCENT_PURPLE, TEXT_PRIMARY,
    TEXT_SECONDARY, NEON_GLOW, SUCCESS, WARNING, ERROR
)


LogFn = Callable[[str, str], None]


class PdfToolsFrameCTk(ctk.CTkFrame):
    def __init__(self, master: ctk.CTkFrame, log: LogFn) -> None:
        super().__init__(master, fg_color="transparent")
        self._log = log
        self.doc: Optional["fitz.Document"] = None
        self.file_path: Optional[Path] = None
        self.current_page: int = 0
        self.zoom: float = 1.0
        self._photo: Optional["ImageTk.PhotoImage"] = None

        self._build()
        i18n.subscribe(self._retranslate)
        self._update_state()

    def _build(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Toolbar with modern buttons
        toolbar = ctk.CTkFrame(
            self,
            fg_color=BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=NEON_GLOW
        )
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        # File operations
        self._btn_open = ctk.CTkButton(
            toolbar,
            text=f"📄 {i18n.t('pdf.open')}",
            command=self.open_pdf,
            corner_radius=8,
            fg_color=ACCENT_CYAN,
            hover_color="#0891b2",
            height=36
        )
        self._btn_open.grid(row=0, column=0, padx=8, pady=8)

        self._btn_save = ctk.CTkButton(
            toolbar,
            text=f"💾 {i18n.t('pdf.save')}",
            command=self.save_pdf,
            corner_radius=8,
            fg_color=SUCCESS,
            hover_color="#059669",
            height=36
        )
        self._btn_save.grid(row=0, column=1, padx=8, pady=8)

        self._btn_close = ctk.CTkButton(
            toolbar,
            text=f"❌ {i18n.t('pdf.close')}",
            command=self.close_pdf,
            corner_radius=8,
            fg_color=ERROR,
            hover_color="#dc2626",
            height=36
        )
        self._btn_close.grid(row=0, column=2, padx=8, pady=8)

        self._btn_merge = ctk.CTkButton(
            toolbar,
            text=f"🔗 {i18n.t('pdf.merge')}",
            command=self.merge_pdfs,
            corner_radius=8,
            fg_color=ACCENT_PURPLE,
            hover_color="#7c3aed",
            height=36
        )
        self._btn_merge.grid(row=0, column=3, padx=8, pady=8)

        # Separator
        sep_frame = ctk.CTkFrame(toolbar, fg_color=NEON_GLOW, width=2)
        sep_frame.grid(row=0, column=4, padx=12, pady=8, sticky="ns")

        # Navigation
        self._btn_prev = ctk.CTkButton(
            toolbar,
            text=i18n.t("pdf.prev"),
            command=self.prev_page,
            corner_radius=8,
            width=100,
            height=36
        )
        self._btn_prev.grid(row=0, column=5, padx=8, pady=8)

        self._page_lbl = ctk.CTkLabel(
            toolbar,
            text="—",
            text_color=TEXT_PRIMARY,
            font=("Segoe UI", 12, "bold")
        )
        self._page_lbl.grid(row=0, column=6, padx=12, pady=8)

        self._btn_next = ctk.CTkButton(
            toolbar,
            text=i18n.t("pdf.next"),
            command=self.next_page,
            corner_radius=8,
            width=100,
            height=36
        )
        self._btn_next.grid(row=0, column=7, padx=8, pady=8)

        # Zoom controls
        self._btn_zin = ctk.CTkButton(
            toolbar,
            text="🔍+",
            command=lambda: self._zoom(1.25),
            corner_radius=8,
            width=60,
            height=36
        )
        self._btn_zin.grid(row=0, column=8, padx=8, pady=8)

        self._btn_zout = ctk.CTkButton(
            toolbar,
            text="🔍−",
            command=lambda: self._zoom(0.8),
            corner_radius=8,
            width=60,
            height=36
        )
        self._btn_zout.grid(row=0, column=9, padx=8, pady=8)

        self._btn_zfit = ctk.CTkButton(
            toolbar,
            text=i18n.t("pdf.zoom.fit"),
            command=self.fit_width,
            corner_radius=8,
            width=100,
            height=36
        )
        self._btn_zfit.grid(row=0, column=10, padx=8, pady=8)

        # Sidebar with page operations
        sidebar = ctk.CTkFrame(
            self,
            fg_color=BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=NEON_GLOW,
            width=200
        )
        sidebar.grid(row=1, column=0, sticky="ns", padx=(0, 12))
        sidebar.grid_propagate(False)

        self._lbl_pages = ctk.CTkLabel(
            sidebar,
            text=f"📑 {i18n.t('pdf.section.pages')}",
            font=("Segoe UI", 14, "bold"),
            text_color=ACCENT_CYAN
        )
        self._lbl_pages.pack(padx=12, pady=(12, 8), anchor="w")

        # Page operation buttons
        self._btn_rot_l = ctk.CTkButton(
            sidebar,
            text=f"↺ {i18n.t('pdf.rotate.left')}",
            command=lambda: self.rotate(-90),
            corner_radius=8,
            fg_color=ACCENT_PURPLE
        )
        self._btn_rot_l.pack(fill="x", padx=12, pady=4)

        self._btn_rot_r = ctk.CTkButton(
            sidebar,
            text=f"↻ {i18n.t('pdf.rotate.right')}",
            command=lambda: self.rotate(90),
            corner_radius=8,
            fg_color=ACCENT_PURPLE
        )
        self._btn_rot_r.pack(fill="x", padx=12, pady=4)

        self._btn_del = ctk.CTkButton(
            sidebar,
            text=f"🗑️ {i18n.t('pdf.delete.page')}",
            command=self.delete_page,
            corner_radius=8,
            fg_color=ERROR
        )
        self._btn_del.pack(fill="x", padx=12, pady=4)

        self._btn_up = ctk.CTkButton(
            sidebar,
            text=i18n.t("pdf.move.up"),
            command=lambda: self.move_page(-1),
            corner_radius=8
        )
        self._btn_up.pack(fill="x", padx=12, pady=4)

        self._btn_down = ctk.CTkButton(
            sidebar,
            text=i18n.t("pdf.move.down"),
            command=lambda: self.move_page(1),
            corner_radius=8
        )
        self._btn_down.pack(fill="x", padx=12, pady=4)

        # Separator
        ctk.CTkFrame(sidebar, fg_color=NEON_GLOW, height=2).pack(
            fill="x", padx=12, pady=12
        )

        # Edit section
        self._lbl_edit = ctk.CTkLabel(
            sidebar,
            text=f"✏️ {i18n.t('pdf.section.edit')}",
            font=("Segoe UI", 14, "bold"),
            text_color=ACCENT_CYAN
        )
        self._lbl_edit.pack(padx=12, pady=(8, 8), anchor="w")

        self._btn_ins_txt = ctk.CTkButton(
            sidebar,
            text=f"📝 {i18n.t('pdf.insert.text')}",
            command=self.insert_text,
            corner_radius=8,
            fg_color=ACCENT_CYAN
        )
        self._btn_ins_txt.pack(fill="x", padx=12, pady=4)

        self._btn_ins_img = ctk.CTkButton(
            sidebar,
            text=f"🖼️ {i18n.t('pdf.insert.image')}",
            command=self.insert_image,
            corner_radius=8,
            fg_color=ACCENT_CYAN
        )
        self._btn_ins_img.pack(fill="x", padx=12, pady=4)

        self._btn_edt_txt = ctk.CTkButton(
            sidebar,
            text=f"✏️ {i18n.t('pdf.edit.text')}",
            command=self.edit_text,
            corner_radius=8,
            fg_color=ACCENT_CYAN
        )
        self._btn_edt_txt.pack(fill="x", padx=12, pady=4)

        # Canvas viewer
        viewer_frame = ctk.CTkFrame(
            self,
            fg_color=BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=NEON_GLOW
        )
        viewer_frame.grid(row=1, column=1, sticky="nsew")
        viewer_frame.grid_columnconfigure(0, weight=1)
        viewer_frame.grid_rowconfigure(0, weight=1)

        # Note: Canvas needs to use tkinter Canvas, not CTk equivalent
        import tkinter as tk
        self.canvas = tk.Canvas(
            viewer_frame,
            background="#0f0e1a",
            highlightthickness=0,
            relief="flat"
        )
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

        # Scrollbars
        vscroll = ctk.CTkScrollbar(viewer_frame, orientation="vertical", command=self.canvas.yview)
        vscroll.grid(row=0, column=1, sticky="ns", padx=(0, 2), pady=2)
        
        hscroll = ctk.CTkScrollbar(viewer_frame, orientation="horizontal", command=self.canvas.xview)
        hscroll.grid(row=1, column=0, sticky="ew", padx=2, pady=(0, 2))
        
        self.canvas.configure(yscrollcommand=vscroll.set, xscrollcommand=hscroll.set)
        self.canvas.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(-1 * (e.delta // 120), "units"))

    def _has_doc(self) -> bool:
        return self.doc is not None and self.doc.page_count > 0

    def _update_state(self) -> None:
        has = self._has_doc()
        state = "normal" if has else "disabled"
        
        buttons = [
            self._btn_save, self._btn_close, self._btn_prev, self._btn_next,
            self._btn_zin, self._btn_zout, self._btn_zfit,
            self._btn_rot_l, self._btn_rot_r, self._btn_del,
            self._btn_up, self._btn_down,
            self._btn_ins_txt, self._btn_ins_img, self._btn_edt_txt
        ]
        
        for btn in buttons:
            btn.configure(state=state)
        
        if has:
            self._page_lbl.configure(
                text=f"{i18n.t('pdf.page')} {self.current_page + 1} {i18n.t('pdf.of')} {self.doc.page_count}"
            )
        else:
            self._page_lbl.configure(text=i18n.t("pdf.no.document"))

    # File operations
    def open_pdf(self) -> None:
        if fitz is None:
            messagebox.showerror(i18n.t("error.title"), "PyMuPDF (fitz) не установлен")
            return
        path = filedialog.askopenfilename(
            title=i18n.t("pdf.open"),
            initialdir=config.get("pdf_last_dir"),
            filetypes=[("PDF", "*.pdf"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self.close_pdf(silent=True)
            self.doc = fitz.open(path)
            self.file_path = Path(path)
            self.current_page = 0
            self.zoom = 1.0
            config.set("pdf_last_dir", str(self.file_path.parent))
            self._log(f"{i18n.t('pdf.opened')} {self.file_path.name}", "ok")
            self._render_page()
        except Exception as exc:
            messagebox.showerror(i18n.t("error.title"), str(exc))
            self._log(str(exc), "error")

    def save_pdf(self) -> None:
        if not self._has_doc():
            return
        target = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            initialdir=config.get("pdf_last_dir"),
            initialfile=(self.file_path.stem + "_edited.pdf") if self.file_path else "output.pdf",
            filetypes=[("PDF", "*.pdf")],
        )
        if not target:
            return
        try:
            self.doc.save(target, garbage=4, deflate=True)
            self._log(f"{i18n.t('pdf.saved')} {Path(target).name}", "ok")
        except Exception as exc:
            messagebox.showerror(i18n.t("error.title"), str(exc))
            self._log(str(exc), "error")

    def close_pdf(self, silent: bool = False) -> None:
        if self.doc is not None:
            try:
                self.doc.close()
            except Exception:
                pass
        self.doc = None
        self.file_path = None
        self.canvas.delete("all")
        self._photo = None
        if not silent:
            self._log("PDF closed", "info")
        self._update_state()

    def merge_pdfs(self) -> None:
        if fitz is None:
            return
        files = filedialog.askopenfilenames(
            title=i18n.t("pdf.merge.title"),
            initialdir=config.get("pdf_last_dir"),
            filetypes=[("PDF", "*.pdf")],
        )
        if not files or len(files) < 2:
            return
        target = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            initialdir=config.get("pdf_last_dir"),
            initialfile="merged.pdf",
            filetypes=[("PDF", "*.pdf")],
        )
        if not target:
            return
        try:
            merged = fitz.open()
            for f in files:
                with fitz.open(f) as src:
                    merged.insert_pdf(src)
            merged.save(target, garbage=4, deflate=True)
            merged.close()
            self._log(f"{i18n.t('pdf.saved')} {Path(target).name} ({len(files)} files)", "ok")
        except Exception as exc:
            messagebox.showerror(i18n.t("error.title"), str(exc))
            self._log(str(exc), "error")

    # Navigation
    def prev_page(self) -> None:
        if self._has_doc() and self.current_page > 0:
            self.current_page -= 1
            self._render_page()

    def next_page(self) -> None:
        if self._has_doc() and self.current_page < self.doc.page_count - 1:
            self.current_page += 1
            self._render_page()

    def _zoom(self, factor: float) -> None:
        if self._has_doc():
            self.zoom = max(0.2, min(6.0, self.zoom * factor))
            self._render_page()

    def fit_width(self) -> None:
        if not self._has_doc():
            return
        page = self.doc[self.current_page]
        cw = max(self.canvas.winfo_width(), 400)
        self.zoom = cw / page.rect.width
        self._render_page()

    def _render_page(self) -> None:
        if not self._has_doc() or Image is None:
            self._update_state()
            return
        page = self.doc[self.current_page]
        mat = fitz.Matrix(self.zoom, self.zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        self._photo = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self._photo, anchor="nw")
        self.canvas.configure(scrollregion=(0, 0, pix.width, pix.height))
        self._update_state()

    # Page operations
    def rotate(self, delta: int) -> None:
        if not self._has_doc():
            return
        page = self.doc[self.current_page]
        page.set_rotation((page.rotation + delta) % 360)
        self._render_page()
        self._log(f"Page {self.current_page + 1} rotated {delta:+d}°", "info")

    def delete_page(self) -> None:
        if not self._has_doc() or self.doc.page_count <= 1:
            messagebox.showinfo(i18n.t("info.title"), "Cannot delete the only page")
            return
        self.doc.delete_page(self.current_page)
        if self.current_page >= self.doc.page_count:
            self.current_page = self.doc.page_count - 1
        self._log(f"Page deleted (remaining {self.doc.page_count})", "info")
        self._render_page()

    def move_page(self, direction: int) -> None:
        if not self._has_doc():
            return
        target = self.current_page + direction
        if not (0 <= target < self.doc.page_count):
            return
        self.doc.move_page(self.current_page, target if direction > 0 else target)
        self.current_page = target
        self._log(f"Page moved to position {target + 1}", "info")
        self._render_page()

    # Editing operations
    def insert_text(self) -> None:
        if not self._has_doc():
            return
        text = simpledialog.askstring(
            i18n.t("pdf.insert.text"),
            i18n.t("pdf.dialog.text"),
            parent=self.winfo_toplevel()
        )
        if not text:
            return
        page = self.doc[self.current_page]
        page.insert_text(fitz.Point(72, 72), text, fontsize=14, fontname="helv", color=(0, 0, 0))
        self._log(f"Text inserted on page {self.current_page + 1}", "ok")
        self._render_page()

    def insert_image(self) -> None:
        if not self._has_doc():
            return
        img_path = filedialog.askopenfilename(
            title=i18n.t("pdf.insert.image"),
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff"), ("All", "*.*")],
        )
        if not img_path:
            return
        page = self.doc[self.current_page]
        rect = fitz.Rect(72, 72, 72 + 300, 72 + 300)
        try:
            page.insert_image(rect, filename=img_path, keep_proportion=True)
            self._log(f"Image inserted on page {self.current_page + 1}", "ok")
            self._render_page()
        except Exception as exc:
            messagebox.showerror(i18n.t("error.title"), str(exc))

    def edit_text(self) -> None:
        if not self._has_doc():
            return
        old = simpledialog.askstring(
            i18n.t("pdf.edit.text"),
            i18n.t("pdf.dialog.oldtext"),
            parent=self.winfo_toplevel()
        )
        if not old:
            return
        new = simpledialog.askstring(
            i18n.t("pdf.edit.text"),
            i18n.t("pdf.dialog.newtext"),
            parent=self.winfo_toplevel()
        )
        if new is None:
            return

        page = self.doc[self.current_page]
        areas = page.search_for(old)
        if not areas:
            messagebox.showinfo(i18n.t("info.title"), "Text not found on this page")
            return
        for rect in areas:
            page.add_redact_annot(rect, fill=(1, 1, 1))
        page.apply_redactions()
        for rect in areas:
            page.insert_text(
                fitz.Point(rect.x0, rect.y1 - 2),
                new,
                fontsize=max(8, rect.height - 2),
                fontname="helv",
                color=(0, 0, 0),
            )
        self._log(f"Replaced {len(areas)} occurrence(s) on page {self.current_page + 1}", "ok")
        self._render_page()

    def _retranslate(self) -> None:
        # Update button texts
        self._btn_open.configure(text=f"📄 {i18n.t('pdf.open')}")
        self._btn_save.configure(text=f"💾 {i18n.t('pdf.save')}")
        self._btn_close.configure(text=f"❌ {i18n.t('pdf.close')}")
        self._btn_merge.configure(text=f"🔗 {i18n.t('pdf.merge')}")
        self._btn_prev.configure(text=i18n.t("pdf.prev"))
        self._btn_next.configure(text=i18n.t("pdf.next"))
        self._btn_zfit.configure(text=i18n.t("pdf.zoom.fit"))
        self._btn_rot_l.configure(text=f"↺ {i18n.t('pdf.rotate.left')}")
        self._btn_rot_r.configure(text=f"↻ {i18n.t('pdf.rotate.right')}")
        self._btn_del.configure(text=f"🗑️ {i18n.t('pdf.delete.page')}")
        self._btn_up.configure(text=i18n.t("pdf.move.up"))
        self._btn_down.configure(text=i18n.t("pdf.move.down"))
        self._btn_ins_txt.configure(text=f"📝 {i18n.t('pdf.insert.text')}")
        self._btn_ins_img.configure(text=f"🖼️ {i18n.t('pdf.insert.image')}")
        self._btn_edt_txt.configure(text=f"✏️ {i18n.t('pdf.edit.text')}")
        
        self._lbl_pages.configure(text=f"📑 {i18n.t('pdf.section.pages')}")
        self._lbl_edit.configure(text=f"✏️ {i18n.t('pdf.section.edit')}")
        
        self._update_state()
