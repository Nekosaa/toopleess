"""PSD Tools tab – Photoshop COM integration (Windows only)."""
from __future__ import annotations

import json
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Optional

from core.config import config
from core.i18n import i18n

LogFn = Callable[[str, str], None]


def _is_windows() -> bool:
    return sys.platform.startswith("win")


class PhotoshopBridge:
    """Small wrapper around the Photoshop COM interface."""

    def __init__(self) -> None:
        self.app = None
        self.available = False
        self._init_error: Optional[str] = None
        if not _is_windows():
            self._init_error = "Photoshop COM is Windows-only."
            return
        try:
            try:
                from win32com.client import gencache  # type: ignore
                self.app = gencache.EnsureDispatch("Photoshop.Application")
            except Exception:
                import win32com.client as com  # type: ignore
                self.app = com.Dispatch("Photoshop.Application")
            self.app.Visible = True
            try:
                self.app.DisplayDialogs = 3
            except Exception:
                pass
            self.available = True
        except Exception as exc:
            self._init_error = self._format_exc(exc)

    @staticmethod
    def _format_exc(exc: BaseException) -> str:
        parts = [f"{type(exc).__name__}: {exc}".strip()]
        info = getattr(exc, "excepinfo", None)
        if info and len(info) >= 3 and info[2]:
            parts.append(str(info[2]).strip())
        return " | ".join(p for p in parts if p)

    def error(self) -> str:
        return self._init_error or ""

    def open(self, path: str):
        try:
            norm = str(Path(path).resolve())
        except Exception:
            norm = path
        try:
            return self.app.Open(norm)
        except Exception as exc:
            raise RuntimeError(self._format_exc(exc)) from exc

    def active_document(self):
        return self.app.ActiveDocument

    # ---- patch: connection health checks --------------------------------
    def is_alive(self) -> bool:
        """Ping Photoshop through a cheap COM property access.

        Returns False if the COM session is dead
        (RPC_S_SERVER_UNAVAILABLE / -2147023174 and similar)."""
        if not self.available or self.app is None:
            return False
        try:
            _ = self.app.Name
            return True
        except Exception:
            return False

    def reset(self) -> None:
        """Drop the dead COM reference so the next _ensure_ps() rebuilds it."""
        self.app = None
        self.available = False
        self._init_error = "Photoshop COM session lost"


class PsdToolsFrame(ttk.Frame):
    def __init__(self, master: tk.Misc, log: LogFn) -> None:
        super().__init__(master, padding=(12, 8))
        self._log = log
        self._ps: Optional[PhotoshopBridge] = None
        self._doc = None
        self._psd_path: Optional[Path] = None
        self._layers_index: list[tuple[str, list[int]]] = []

        self._mode_var = tk.StringVar(value=config.get("psd_mode", "fit"))
        self._no_upscale_var = tk.BooleanVar(value=bool(config.get("psd_no_upscale", True)))
        self._clip_bounds_var = tk.BooleanVar(value=bool(config.get("psd_clip_to_bounds", True)))
        self._in_var = tk.StringVar(value=config.get("psd_in_dir"))
        self._out_var = tk.StringVar(value=config.get("psd_out_dir"))

        # Persist UI state on every change so the next launch restores it.
        self._mode_var.trace_add("write",
            lambda *_: config.set("psd_mode", self._mode_var.get()))
        self._no_upscale_var.trace_add("write",
            lambda *_: config.set("psd_no_upscale", bool(self._no_upscale_var.get())))
        self._clip_bounds_var.trace_add("write",
            lambda *_: config.set("psd_clip_to_bounds", bool(self._clip_bounds_var.get())))
        self._in_var.trace_add("write",
            lambda *_: config.set("psd_in_dir", self._in_var.get()))
        self._out_var.trace_add("write",
            lambda *_: config.set("psd_out_dir", self._out_var.get()))

        self._build()
        i18n.subscribe(self._retranslate)

    def _build(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        # Toolbar
        toolbar = ttk.Frame(self)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        self._btn_open  = ttk.Button(toolbar, text=i18n.t("psd.open"),    command=self.open_psd)
        self._btn_scan  = ttk.Button(toolbar, text=i18n.t("psd.scan"),    command=self.scan_layers)
        self._btn_unlck = ttk.Button(toolbar, text=i18n.t("psd.unlock"),  command=self.unlock_all)
        self._btn_repl  = ttk.Button(toolbar, text=i18n.t("psd.replace"), command=self.replace_in_selected)
        for i, b in enumerate((self._btn_open, self._btn_scan, self._btn_unlck, self._btn_repl)):
            b.grid(row=0, column=i, padx=(0, 6))

        # Left – layers list
        left = ttk.Frame(self)
        left.grid(row=1, column=0, sticky="ns", padx=(0, 12))

        self._lbl_layers = ttk.Label(left, text=i18n.t("psd.section.layers"),
                                     font=("Segoe UI", 10, "bold"))
        self._lbl_layers.pack(anchor="w", pady=(0, 6))

        self._listbox = tk.Listbox(left, width=42, height=22, activestyle="dotbox")
        self._listbox.pack(fill="y", expand=False)

        sb = ttk.Scrollbar(left, orient="vertical", command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=sb.set)

        # Right – actions + batch
        right = ttk.Frame(self)
        right.grid(row=1, column=1, sticky="nsew")
        right.columnconfigure(1, weight=1)

        self._lbl_actions = ttk.Label(right, text=i18n.t("psd.section.actions"),
                                      font=("Segoe UI", 10, "bold"))
        self._lbl_actions.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

        self._lbl_mode = ttk.Label(right, text=i18n.t("psd.mode"))
        self._lbl_mode.grid(row=1, column=0, sticky="w", pady=4)
        self._rb_fit  = ttk.Radiobutton(right, text=i18n.t("psd.mode.fit"),
                                        variable=self._mode_var, value="fit")
        self._rb_fill = ttk.Radiobutton(right, text=i18n.t("psd.mode.fill"),
                                        variable=self._mode_var, value="fill")
        self._rb_orig = ttk.Radiobutton(right, text=i18n.t("psd.mode.original"),
                                        variable=self._mode_var, value="original")
        self._rb_fit.grid(row=1, column=1, sticky="w")
        self._rb_fill.grid(row=1, column=2, sticky="w")
        self._rb_orig.grid(row=1, column=3, sticky="w")

        self._lbl_mode_hint = ttk.Label(right, text=i18n.t("psd.mode.hint"),
                                        foreground="#888", wraplength=520, justify="left")
        self._lbl_mode_hint.grid(row=2, column=0, columnspan=4, sticky="w", pady=(2, 0))

        # --- extra options: preserved between launches ---------------------
        self._cb_no_upscale = ttk.Checkbutton(
            right, text=i18n.t("psd.no.upscale"),
            variable=self._no_upscale_var,
        )
        self._cb_no_upscale.grid(row=3, column=0, columnspan=4, sticky="w", pady=(6, 0))

        self._cb_clip_bounds = ttk.Checkbutton(
            right, text=i18n.t("psd.clip.bounds"),
            variable=self._clip_bounds_var,
        )
        self._cb_clip_bounds.grid(row=4, column=0, columnspan=4, sticky="w", pady=(2, 0))

        ttk.Separator(right, orient="horizontal").grid(
            row=5, column=0, columnspan=4, sticky="ew", pady=12,
        )

        self._lbl_batch = ttk.Label(right, text=i18n.t("psd.section.batch"),
                                    font=("Segoe UI", 10, "bold"))
        self._lbl_batch.grid(row=6, column=0, columnspan=4, sticky="w", pady=(0, 8))

        self._lbl_in = ttk.Label(right, text=i18n.t("psd.in.folder"))
        self._lbl_in.grid(row=7, column=0, sticky="w")
        ttk.Entry(right, textvariable=self._in_var).grid(row=7, column=1, columnspan=2, sticky="ew", padx=6)
        self._btn_in = ttk.Button(right, text=i18n.t("common.browse"),
                                  command=lambda: self._pick(self._in_var, "psd_in_dir"))
        self._btn_in.grid(row=7, column=3, sticky="w")

        self._lbl_out = ttk.Label(right, text=i18n.t("psd.out.folder"))
        self._lbl_out.grid(row=8, column=0, sticky="w", pady=4)
        ttk.Entry(right, textvariable=self._out_var).grid(row=8, column=1, columnspan=2, sticky="ew", padx=6, pady=4)
        self._btn_out = ttk.Button(right, text=i18n.t("common.browse"),
                                   command=lambda: self._pick(self._out_var, "psd_out_dir"))
        self._btn_out.grid(row=8, column=3, sticky="w", pady=4)

        self._btn_batch = ttk.Button(right, text=i18n.t("psd.batch"),
                                     command=self.batch_replace)
        self._btn_batch.grid(row=9, column=0, columnspan=4, sticky="ew", pady=(12, 0))

        # Warning banner
        self._warn = ttk.Label(self, text="", foreground="#c05555")
        self._warn.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))

    def _pick(self, var: tk.StringVar, cfg_key: str) -> None:
        chosen = filedialog.askdirectory(initialdir=var.get() or str(Path.home()))
        if chosen:
            var.set(chosen)
            config.set(cfg_key, chosen)

    # ------------------------------------------------------------------
    # Photoshop init (lazy)
    # ------------------------------------------------------------------
    def _ensure_ps(self) -> bool:
        # Recreate the bridge if we have none or the COM session is dead.
        if self._ps is None or not self._ps.is_alive():
            if self._ps is not None and not self._ps.is_alive():
                self._log("Photoshop connection lost – reconnecting…", "warn")
                try:
                    self._ps.reset()
                except Exception:
                    pass
                self._doc = None
                self._psd_path = None
            try:
                self._ps = PhotoshopBridge()
            except Exception as exc:
                self._log(f"Photoshop bridge init failed: {exc}", "error")
                self._ps = None

        if self._ps is None or not self._ps.available:
            err = self._ps.error() if self._ps is not None else "no bridge"
            self._warn.configure(text=f"{i18n.t('psd.no.photoshop')}  ({err})")
            self._log(i18n.t("psd.no.photoshop"), "error")
            return False

        self._warn.configure(text="")
        try:
            self._ps.app.BringToFront()
        except Exception:
            pass
        return True

    # ------------------------------------------------------------------
    # File
    # ------------------------------------------------------------------
    def open_psd(self) -> None:
        import time

        if not self._ensure_ps():
            return
        path = filedialog.askopenfilename(
            title=i18n.t("psd.open"),
            initialdir=config.get("psd_in_dir"),
            filetypes=[("Photoshop", "*.psd *.psb"), ("All files", "*.*")],
        )
        if not path:
            return

        last_exc: Optional[BaseException] = None
        for attempt in range(3):
            try:
                self._doc = self._ps.open(path)
                self._psd_path = Path(path)
                config.set("psd_in_dir", str(self._psd_path.parent))
                self._log(f"Opened: {self._psd_path.name}", "ok")
                self.scan_layers()
                return
            except Exception as exc:
                last_exc = exc
                msg = (str(exc) or exc.__class__.__name__)
                low = msg.lower()
                is_rpc = (
                    "-2147023174" in msg
                    or "rpc" in low
                    or "недоступен" in low
                    or "server unavailable" in low
                )
                if is_rpc and attempt < 2:
                    self._log(
                        f"RPC error on attempt {attempt + 1}/3 – reconnecting…",
                        "warn",
                    )
                    try:
                        if self._ps is not None:
                            self._ps.reset()
                    except Exception:
                        pass
                    self._doc = None
                    self._psd_path = None
                    time.sleep(1.0)
                    if not self._ensure_ps():
                        break
                    continue
                break

        msg = (str(last_exc) or last_exc.__class__.__name__) if last_exc else "unknown"
        hint = (
            "\n\nВозможные причины:\n"
            "  • Photoshop закрыт или ещё не готов — откройте его вручную и повторите\n"
            "  • В Photoshop открыт модальный диалог (Missing Fonts, Camera Raw и т.п.) — закройте его\n"
            "  • Файл сейчас открыт/заблокирован (OneDrive/Dropbox sync)\n"
            "  • Путь содержит символы, которых Photoshop не понимает —\n"
            "    попробуйте короткий латинский путь (например C:\\test\\file.psd)\n"
            "  • Photoshop показывает «Missing Fonts / Color Profile» — сначала\n"
            "    откройте файл вручную и ответьте на его вопросы"
        )
        messagebox.showerror(i18n.t("error.title"), f"{msg}{hint}")
        self._log(msg, "error")

    # ------------------------------------------------------------------
    # Scan / unlock
    # ------------------------------------------------------------------
    def scan_layers(self) -> None:
        if not self._ensure_ps() or self._doc is None:
            self._log(i18n.t("psd.no.file"), "warn")
            return
        self._layers_index.clear()
        self._listbox.delete(0, "end")
        max_depth = int(config.get("smart_object_depth", 3))
        self._walk(self._doc, path=[], depth=0, max_depth=max_depth)
        self._log(f"Layers scanned: {len(self._layers_index)}", "info")

    def _walk(self, container, path: list[int], depth: int, max_depth: int) -> None:
        try:
            layer_count = container.Layers.Count
        except Exception:
            return
        for i in range(1, layer_count + 1):
            layer = container.Layers.Item(i)
            name = getattr(layer, "Name", f"Layer {i}")
            indent = "  " * depth
            try:
                kind = getattr(layer, "Kind", None)  # 17 = smart object
            except Exception:
                kind = None
            marker = "  [SO]" if kind == 17 else ""
            self._listbox.insert("end", f"{indent}{name}{marker}")
            self._layers_index.append((name, path + [i]))

            try:
                is_group = layer.Typename == "LayerSet"
            except Exception:
                is_group = False
            if is_group and depth < max_depth:
                self._walk(layer, path + [i], depth + 1, max_depth)

    def unlock_all(self) -> None:
        if not self._ensure_ps() or self._doc is None:
            self._log(i18n.t("psd.no.file"), "warn")
            return
        count = self._unlock_recursive(self._doc, depth=0,
                                       max_depth=int(config.get("smart_object_depth", 3)))
        self._log(f"Unlocked {count} layers", "ok")

    def _unlock_recursive(self, container, depth: int, max_depth: int) -> int:
        unlocked = 0
        try:
            layer_count = container.Layers.Count
        except Exception:
            return 0
        for i in range(1, layer_count + 1):
            layer = container.Layers.Item(i)
            for prop in ("AllLocked", "PixelsLocked", "PositionLocked", "TransparentPixelsLocked"):
                try:
                    setattr(layer, prop, False)
                    unlocked += 1
                except Exception:
                    pass
            try:
                if layer.Typename == "LayerSet" and depth < max_depth:
                    unlocked += self._unlock_recursive(layer, depth + 1, max_depth)
            except Exception:
                pass
        return unlocked

    # ------------------------------------------------------------------
    # Replace photo in Smart Object
    # ------------------------------------------------------------------
    def replace_in_selected(self) -> None:
        if not self._ensure_ps() or self._doc is None:
            self._log(i18n.t("psd.no.file"), "warn")
            return
        sel = self._listbox.curselection()
        if not sel:
            messagebox.showinfo(i18n.t("info.title"), i18n.t("psd.select.layer"))
            return
        name, path = self._layers_index[sel[0]]
        image_path = filedialog.askopenfilename(
            title=i18n.t("psd.replace"),
            filetypes=[("Images", "*.jpg *.jpeg *.png *.tif *.tiff *.bmp"), ("All", "*.*")],
        )
        if not image_path:
            return
        try:
            layer = self._resolve_layer(path)
            self._replace_layer_content(layer, image_path, self._mode_var.get())
            self._log(f"Replaced photo in '{name}'", "ok")
        except Exception as exc:
            messagebox.showerror(i18n.t("error.title"), str(exc))
            self._log(str(exc), "error")

    def _resolve_layer(self, path: list[int]):
        node = self._doc
        for idx in path:
            node = node.Layers.Item(idx)
        return node

    def _replace_smart_object(self, so_layer, image_path: str, mode: str) -> None:
        self._doc.ActiveLayer = so_layer

        js_open = (
            'try{executeAction(stringIDToTypeID("placedLayerEditContents"),'
            ' undefined, DialogModes.NO);}catch(e){}'
        )
        self._ps.app.DoJavaScript(js_open)

        so_doc = self._ps.app.ActiveDocument
        try:
            self._activate_target_raster_in_active_doc()
            self._run_merge_down_jsx(image_path, mode)
            so_doc.Save()
        finally:
            so_doc.Close(2)  # 2 = SaveOptions.DONOTSAVECHANGES

    def _activate_target_raster_in_active_doc(self) -> None:
        jsx = r"""
        (function () {
            var doc = app.activeDocument;
            function pick(container) {
                for (var i = 0; i < container.artLayers.length; i++) {
                    var L = container.artLayers[i];
                    try {
                        if (L.kind === LayerKind.SMARTOBJECT) continue;
                    } catch (e) {}
                    try {
                        var b = L.bounds;
                        var w = b[2].as('px') - b[0].as('px');
                        var h = b[3].as('px') - b[1].as('px');
                        if (w > 0 && h > 0) return L;
                    } catch (e) { return L; }
                }
                if (container.artLayers.length > 0) return container.artLayers[0];
                for (var g = 0; g < container.layerSets.length; g++) {
                    var found = pick(container.layerSets[g]);
                    if (found) return found;
                }
                return null;
            }
            var target = pick(doc);
            if (target) doc.activeLayer = target;
        })();
        """
        self._ps.app.DoJavaScript(jsx)

    def _replace_layer_content(self, layer, image_path: str, mode: str) -> None:
        try:
            kind = getattr(layer, "Kind", None)  # 17 = SmartObjectLayer
        except Exception:
            kind = None
        try:
            typename = getattr(layer, "Typename", "")
        except Exception:
            typename = ""

        is_smart_object = (kind == 17)
        is_group = (typename == "LayerSet")

        if is_group:
            raise RuntimeError("Selected item is a group (LayerSet), not a photo layer.")

        if is_smart_object:
            self._replace_smart_object(layer, image_path, mode)
        else:
            self._replace_raster_merge_down(layer, image_path, mode)

    def _replace_raster_merge_down(self, layer, image_path: str, mode: str) -> None:
        self._doc.ActiveLayer = layer
        self._run_merge_down_jsx(image_path, mode)

    def _run_merge_down_jsx(self, image_path: str, mode: str) -> None:
        """Core merge-down algorithm — runs on the CURRENTLY ACTIVE layer
        of the CURRENTLY ACTIVE document.

        Preserves: layer name, blend mode, opacity + fill opacity, layer effects.

        Extra options (persisted in config, read at call time):
             • psd_no_upscale       – clamp scale <= 1.0 (fit / fill only)
             • psd_clip_to_bounds   – clear placed pixels outside target bounds
        """
        path_literal = json.dumps(str(Path(image_path)))
        mode_literal = json.dumps(mode)
        no_upscale_literal = "true" if bool(config.get("psd_no_upscale", True)) else "false"
        clip_literal = "true" if bool(config.get("psd_clip_to_bounds", True)) else "false"

        jsx = r"""
        (function () {
            var NEW_PATH   = __PATH__;
            var MODE       = __MODE__;
            var NO_UPSCALE = __NO_UPSCALE__;
            var CLIP       = __CLIP__;

            var doc = app.activeDocument;
            var target = doc.activeLayer;

            var targetName = target.name;

            var savedRulerUnits = app.preferences.rulerUnits;
            var savedTypeUnits  = app.preferences.typeUnits;
            app.preferences.rulerUnits = Units.PIXELS;
            app.preferences.typeUnits  = TypeUnits.PIXELS;

            function asPx(v){ try { return v.as('px'); } catch(e){ return Number(v); } }

            var b = target.bounds;
            var L = asPx(b[0]), T = asPx(b[1]), R = asPx(b[2]), Bt = asPx(b[3]);
            var W = R - L, H = Bt - T;

            if (W <= 0 || H <= 0) {
                app.preferences.rulerUnits = savedRulerUnits;
                app.preferences.typeUnits  = savedTypeUnits;
                throw new Error("Target layer has empty bounds; nothing to replace.");
            }

            try { target.allLocked                = false; } catch(e) {}
            try { target.pixelsLocked             = false; } catch(e) {}
            try { target.positionLocked           = false; } catch(e) {}
            try { target.transparentPixelsLocked  = false; } catch(e) {}

            doc.activeLayer = target;
            doc.selection.select([[L,T],[R,T],[R,Bt],[L,Bt]], SelectionType.REPLACE);
            try { doc.selection.clear(); } catch(e) {}
            try { doc.selection.deselect(); } catch(e) {}

            var f = new File(NEW_PATH);
            var d = new ActionDescriptor();
            d.putPath(charIDToTypeID('null'), f);
            d.putEnumerated(charIDToTypeID('FTcs'), charIDToTypeID('QCSt'), charIDToTypeID('Qcsa'));
            executeAction(charIDToTypeID('Plc '), d, DialogModes.NO);
            var placed = doc.activeLayer;

            var pb = placed.bounds;
            var pw = asPx(pb[2]) - asPx(pb[0]);
            var ph = asPx(pb[3]) - asPx(pb[1]);

            if (pw > 0 && ph > 0 && MODE !== 'original') {
                var scale;
                if (MODE === 'fill') {
                    scale = Math.max(W / pw, H / ph);
                } else {
                    scale = Math.min(W / pw, H / ph);
                }
                // "Don't upscale" – keep sharpness of small photos.
                if (NO_UPSCALE && scale > 1.0) scale = 1.0;
                var pct = scale * 100.0;
                placed.resize(pct, pct, AnchorPosition.MIDDLECENTER);
            }

            pb = placed.bounds;
            var cx = (asPx(pb[0]) + asPx(pb[2])) / 2;
            var cy = (asPx(pb[1]) + asPx(pb[3])) / 2;
            var tcx = (L + R) / 2;
            var tcy = (T + Bt) / 2;
            placed.translate(tcx - cx, tcy - cy);

            try { placed.rasterize(RasterizeType.ENTIRELAYER); } catch(e) {}

            // Clip placed to target's rectangular bounds → result stays
            // exactly inside the old rectangle "as if nothing was replaced".
            if (CLIP) {
                try {
                    doc.selection.select(
                        [[L,T],[R,T],[R,Bt],[L,Bt]],
                        SelectionType.REPLACE
                    );
                    doc.selection.invert();
                    doc.activeLayer = placed;
                    try { doc.selection.clear(); } catch(e) {}
                    try { doc.selection.deselect(); } catch(e) {}
                } catch(e) {}
            }

            // Merge Down onto target – preserves target's name, blend mode,
            // opacity and effects.
            placed.merge();

            try { doc.activeLayer.name = targetName; } catch(e) {}

            app.preferences.rulerUnits = savedRulerUnits;
            app.preferences.typeUnits  = savedTypeUnits;
        })();
        """
        jsx = (jsx
               .replace("__PATH__", path_literal)
               .replace("__MODE__", mode_literal)
               .replace("__NO_UPSCALE__", no_upscale_literal)
               .replace("__CLIP__", clip_literal))
        self._ps.app.DoJavaScript(jsx)

    # ------------------------------------------------------------------
    # Batch replace
    # ------------------------------------------------------------------
    def batch_replace(self) -> None:
        if not self._ensure_ps():
            return
        in_dir = Path(self._in_var.get() or "")
        out_dir = Path(self._out_var.get() or "")
        if not in_dir.is_dir():
            messagebox.showerror(i18n.t("error.title"), f"Bad in-folder: {in_dir}")
            return
        out_dir.mkdir(parents=True, exist_ok=True)
        images = [p for p in in_dir.iterdir()
                  if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp")]
        if not images:
            messagebox.showinfo(i18n.t("info.title"), "No images found in in-folder")
            return
        sel = self._listbox.curselection()
        if not sel:
            messagebox.showinfo(i18n.t("info.title"), i18n.t("psd.select.layer"))
            return
        name, path = self._layers_index[sel[0]]

        if self._doc is None or self._psd_path is None:
            self._log(i18n.t("psd.no.file"), "warn")
            return

        self._log(f"Batch: {len(images)} image(s) → layer '{name}'", "info")
        for img in images:
            try:
                layer = self._resolve_layer(path)
                self._replace_layer_content(layer, str(img), self._mode_var.get())
                target = out_dir / f"{self._psd_path.stem}__{img.stem}.psd"
                self._doc.SaveAs(str(target))
                self._log(f"Saved: {target.name}", "ok")
            except Exception as exc:
                self._log(f"{img.name}: {exc}", "error")
        self._log(i18n.t("psd.done"), "ok")

    # ------------------------------------------------------------------
    # i18n
    # ------------------------------------------------------------------
    def _retranslate(self) -> None:
        pairs = [
            (self._btn_open,  "psd.open"),
            (self._btn_scan,  "psd.scan"),
            (self._btn_unlck, "psd.unlock"),
            (self._btn_repl,  "psd.replace"),
            (self._btn_batch, "psd.batch"),
            (self._btn_in,    "common.browse"),
            (self._btn_out,   "common.browse"),
            (self._rb_fit,    "psd.mode.fit"),
            (self._rb_fill,   "psd.mode.fill"),
            (self._rb_orig,   "psd.mode.original"),
            (self._cb_no_upscale,  "psd.no.upscale"),
            (self._cb_clip_bounds, "psd.clip.bounds"),
        ]
        for widget, key in pairs:
            widget.configure(text=i18n.t(key))
        self._lbl_layers.configure(text=i18n.t("psd.section.layers"))
        self._lbl_actions.configure(text=i18n.t("psd.section.actions"))
        self._lbl_batch.configure(text=i18n.t("psd.section.batch"))
        self._lbl_mode.configure(text=i18n.t("psd.mode"))
        self._lbl_mode_hint.configure(text=i18n.t("psd.mode.hint"))
        self._lbl_in.configure(text=i18n.t("psd.in.folder"))
        self._lbl_out.configure(text=i18n.t("psd.out.folder"))
        if self._ps and not self._ps.available:
            self._warn.configure(text=f"{i18n.t('psd.no.photoshop')}  ({self._ps.error()})")
