"""PDF Tools tab – built on PyMuPDF (fitz) + Pillow."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
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


LogFn = Callable[[str, str], None]


class PdfToolsFrame(ttk.Frame):
    def __init__(self, master: tk.Misc, log: LogFn) -> None:
        super().__init__(master, padding=(12, 8))
        self._log = log
        self.doc: Optional["fitz.Document"] = None
        self.file_path: Optional[Path] = None
        self.current_page: int = 0
        self.zoom: float = 1.0
        self._photo: Optional["ImageTk.PhotoImage"] = None

        self._build()
        i18n.subscribe(self._retranslate)
        self._update_state()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        # Toolbar
        toolbar = ttk.Frame(self)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        self._btn_open   = ttk.Button(toolbar, text=i18n.t("pdf.open"),   command=self.open_pdf)
        self._btn_save   = ttk.Button(toolbar, text=i18n.t("pdf.save"),   command=self.save_pdf)
        self._btn_close  = ttk.Button(toolbar, text=i18n.t("pdf.close"),  command=self.close_pdf)
        self._btn_merge  = ttk.Button(toolbar, text=i18n.t("pdf.merge"),  command=self.merge_pdfs)
        for i, b in enumerate((self._btn_open, self._btn_save, self._btn_close, self._btn_merge)):
            b.grid(row=0, column=i, padx=(0, 6))

        ttk.Separator(toolbar, orient="vertical").grid(row=0, column=4, sticky="ns", padx=8)

        self._btn_prev   = ttk.Button(toolbar, text=i18n.t("pdf.prev"),      command=self.prev_page)
        self._btn_next   = ttk.Button(toolbar, text=i18n.t("pdf.next"),      command=self.next_page)
        self._page_lbl   = ttk.Label(toolbar, text="—")
        self._btn_zin    = ttk.Button(toolbar, text="+", width=3, command=lambda: self._zoom(1.25))
        self._btn_zout   = ttk.Button(toolbar, text="−", width=3, command=lambda: self._zoom(0.8))
        self._btn_zfit   = ttk.Button(toolbar, text=i18n.t("pdf.zoom.fit"),  command=self.fit_width)
        for i, w in enumerate((self._btn_prev, self._page_lbl, self._btn_next,
                               self._btn_zin, self._btn_zout, self._btn_zfit), start=5):
            w.grid(row=0, column=i, padx=(0, 6))

        # Side panel
        side = ttk.Frame(self)
        side.grid(row=1, column=0, sticky="ns", padx=(0, 12))

        self._lbl_pages = ttk.Label(side, text=i18n.t("pdf.section.pages"),
                                    font=("Segoe UI", 10, "bold"))
        self._lbl_pages.pack(anchor="w", pady=(0, 6))

        self._btn_rot_l = ttk.Button(side, text=i18n.t("pdf.rotate.left"),  command=lambda: self.rotate(-90))
        self._btn_rot_r = ttk.Button(side, text=i18n.t("pdf.rotate.right"), command=lambda: self.rotate(90))
        self._btn_del   = ttk.Button(side, text=i18n.t("pdf.delete.page"),  command=self.delete_page)
        self._btn_up    = ttk.Button(side, text=i18n.t("pdf.move.up"),      command=lambda: self.move_page(-1))
        self._btn_down  = ttk.Button(side, text=i18n.t("pdf.move.down"),    command=lambda: self.move_page(1))
        for b in (self._btn_rot_l, self._btn_rot_r, self._btn_del, self._btn_up, self._btn_down):
            b.pack(fill="x", pady=2)

        ttk.Separator(side, orient="horizontal").pack(fill="x", pady=10)

        self._lbl_edit = ttk.Label(side, text=i18n.t("pdf.section.edit"),
                                   font=("Segoe UI", 10, "bold"))
        self._lbl_edit.pack(anchor="w", pady=(0, 6))

        self._btn_ins_txt = ttk.Button(side, text=i18n.t("pdf.insert.text"),  command=self.insert_text)
        self._btn_ins_img = ttk.Button(side, text=i18n.t("pdf.insert.image"), command=self.insert_image)
        self._btn_edt_txt = ttk.Button(side, text=i18n.t("pdf.edit.text"),    command=self.edit_text)
        for b in (self._btn_ins_txt, self._btn_ins_img, self._btn_edt_txt):
            b.pack(fill="x", pady=2)

        # Canvas viewer
        viewer = ttk.Frame(self, relief="sunken", borderwidth=1)
        viewer.grid(row=1, column=1, sticky="nsew")
        viewer.columnconfigure(0, weight=1)
        viewer.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(viewer, background="#2a2a2a", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        vscroll = ttk.Scrollbar(viewer, orient="vertical", command=self.canvas.yview)
        vscroll.grid(row=0, column=1, sticky="ns")
        hscroll = ttk.Scrollbar(viewer, orient="horizontal", command=self.canvas.xview)
        hscroll.grid(row=1, column=0, sticky="ew")
        self.canvas.configure(yscrollcommand=vscroll.set, xscrollcommand=hscroll.set)
        self.canvas.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(-1 * (e.delta // 120), "units"))

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------
    def _has_doc(self) -> bool:
        return self.doc is not None and self.doc.page_count > 0

    def _update_state(self) -> None:
        has = self._has_doc()
        state = "normal" if has else "disabled"
        for b in (self._btn_save, self._btn_close, self._btn_prev, self._btn_next,
                  self._btn_zin, self._btn_zout, self._btn_zfit,
                  self._btn_rot_l, self._btn_rot_r, self._btn_del,
                  self._btn_up, self._btn_down,
                  self._btn_ins_txt, self._btn_ins_img, self._btn_edt_txt):
            b.configure(state=state)
        if has:
            self._page_lbl.configure(
                text=f"{i18n.t('pdf.page')} {self.current_page + 1} {i18n.t('pdf.of')} {self.doc.page_count}"
            )
        else:
            self._page_lbl.configure(text=i18n.t("pdf.no.document"))

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Navigation & rendering
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Page operations
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Editing
    # ------------------------------------------------------------------
    def insert_text(self) -> None:
        if not self._has_doc():
            return
        text = simpledialog.askstring(i18n.t("pdf.insert.text"),
                                      i18n.t("pdf.dialog.text"), parent=self)
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
        """Replace-existing-text via redact + insert."""
        if not self._has_doc():
            return
        old = simpledialog.askstring(i18n.t("pdf.edit.text"),
                                     i18n.t("pdf.dialog.oldtext"), parent=self)
        if not old:
            return
        new = simpledialog.askstring(i18n.t("pdf.edit.text"),
                                     i18n.t("pdf.dialog.newtext"), parent=self)
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

    # ------------------------------------------------------------------
    # i18n
    # ------------------------------------------------------------------
    def _retranslate(self) -> None:
        pairs = [
            (self._btn_open,    "pdf.open"),
            (self._btn_save,    "pdf.save"),
            (self._btn_close,   "pdf.close"),
            (self._btn_merge,   "pdf.merge"),
            (self._btn_prev,    "pdf.prev"),
            (self._btn_next,    "pdf.next"),
            (self._btn_zfit,    "pdf.zoom.fit"),
            (self._btn_rot_l,   "pdf.rotate.left"),
            (self._btn_rot_r,   "pdf.rotate.right"),
            (self._btn_del,     "pdf.delete.page"),
            (self._btn_up,      "pdf.move.up"),
            (self._btn_down,    "pdf.move.down"),
            (self._btn_ins_txt, "pdf.insert.text"),
            (self._btn_ins_img, "pdf.insert.image"),
            (self._btn_edt_txt, "pdf.edit.text"),
        ]
        for widget, key in pairs:
            widget.configure(text=i18n.t(key))
        self._lbl_pages.configure(text=i18n.t("pdf.section.pages"))
        self._lbl_edit.configure(text=i18n.t("pdf.section.edit"))
        self._update_state()
