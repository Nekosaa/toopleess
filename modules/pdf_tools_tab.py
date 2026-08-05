"""PSD Tools Tab - Photoshop COM logic (with DPI-aware SO replacement)."""
from __future__ import annotations

import csv
import json
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Optional

from core.config import config
from core.i18n import i18n

from modules.image_replace import resize_with_mode, prepare_for_smart_object
from modules.so_picker import SOPickerWindow

try:
    from PIL import Image, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


LogFn = Callable[[str, str], None]


def _is_windows() -> bool:
    return sys.platform.startswith("win")


def _is_group(layer) -> bool:
    for attr in ("LayerSets", "ArtLayers", "Layers"):
        try:
            _ = getattr(layer, attr).Count
            return True
        except Exception:
            continue
    try:
        tn = str(getattr(layer, "Typename", "")).lower()
        if "layerset" in tn or tn in ("set", "group"):
            return True
    except Exception:
        pass
    try:
        _ = int(getattr(layer, "Kind"))
        return False
    except Exception:
        return True


def _is_smart_object(layer) -> bool:
    try:
        k = getattr(layer, "Kind", None)
        if k is not None and int(k) == 17:
            return True
    except Exception:
        pass
    try:
        return "smart" in str(getattr(layer, "Typename", "")).lower()
    except Exception:
        return False


class PhotoshopBridge:
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

    def is_alive(self) -> bool:
        if not self.available or self.app is None:
            return False
        try:
            _ = self.app.Name
            return True
        except Exception:
            return False

    def reset(self) -> None:
        self.app = None
        self.available = False
        self._init_error = "Photoshop COM session lost"


class PsdToolsFrame(ttk.Frame):
    _PHOTO_KEYWORDS = (
        "photo edit", "photo", "фото", "foto", "portrait", "портрет",
        "avatar", "аватар", "headshot", "image edit", "image",
        "снимок", "picture", "pic", "user photo", "your photo",
    )
    _PHOTO_SO_NAMES = ("photo edit", "наложение", "edit small photo")
    _MIN_SOURCE_SIDE = 400

    def __init__(self, master, log: LogFn) -> None:
        super().__init__(master)
        self._log = log
        self._ps = PhotoshopBridge()
        self._doc = None
        self._psd_path: Optional[Path] = None
        self._layers: list[tuple[str, list]] = []
        self._so_frames: dict[str, tuple[float, float, float, float]] = {}
        self._small_source_ack = False

        self._build()
        i18n.subscribe(self._retranslate)

        if not self._ps.available:
            self._log(f"Photoshop COM unavailable: {self._ps.error()}", "error")

    # ----- UI (unchanged) -----
    def _build(self) -> None:
        main = ttk.Frame(self, padding=10)
        main.pack(fill="both", expand=True)

        if self._ps and not self._ps.available:
            self._warn = ttk.Label(main, text=f"{i18n.t('psd.no.photoshop')}", foreground="red")
            self._warn.pack(pady=10)
        else:
            self._warn = None

        row0 = ttk.Frame(main); row0.pack(fill="x", pady=5)
        self._btn_open = ttk.Button(row0, text=i18n.t("psd.open"), command=self.open_psd); self._btn_open.pack(side="left", padx=5)
        self._btn_scan = ttk.Button(row0, text=i18n.t("psd.scan"), command=self.scan_layers); self._btn_scan.pack(side="left", padx=5)
        self._btn_unlck = ttk.Button(row0, text=i18n.t("psd.unlock"), command=self.unlock_layers); self._btn_unlck.pack(side="left", padx=5)

        ttk.Label(main, text=i18n.t("psd.section.layers")).pack(anchor="w", pady=(10, 2))
        frame_list = ttk.Frame(main); frame_list.pack(fill="both", expand=True)
        sb = ttk.Scrollbar(frame_list, orient="vertical"); sb.pack(side="right", fill="y")
        self._tree = ttk.Treeview(frame_list, columns=("type",), show="tree headings", yscrollcommand=sb.set)
        self._tree.heading("#0", text="Layer"); self._tree.heading("type", text="Type")
        self._tree.column("type", width=80); self._tree.pack(side="left", fill="both", expand=True)
        sb.config(command=self._tree.yview)

        ttk.Label(main, text=i18n.t("psd.section.actions")).pack(anchor="w", pady=(10, 2))
        row_act = ttk.Frame(main); row_act.pack(fill="x", pady=5)
        self._btn_repl = ttk.Button(row_act, text=i18n.t("psd.replace"), command=self.replace_selected); self._btn_repl.pack(side="left", padx=5)
        self._btn_auto = ttk.Button(row_act, text="Авто фото", command=self.auto_replace_photo); self._btn_auto.pack(side="left", padx=5)
        self._btn_picker = ttk.Button(row_act, text="Выбор SO", command=self.pick_so_and_replace); self._btn_picker.pack(side="left", padx=5)
        self._btn_all_so = ttk.Button(row_act, text="Во все SO", command=self.replace_all_photo_so); self._btn_all_so.pack(side="left", padx=5)

        ttk.Label(main, text=i18n.t("psd.mode")).pack(anchor="w", pady=(10, 2))
        # ВАЖНО: дефолт для SO = fill/cover, чтобы мини-фото вставало как оригинал
        self._mode_var = tk.StringVar(value=config.get("psd_mode", "fill"))
        row_mode = ttk.Frame(main); row_mode.pack(fill="x")
        self._rb_fit = ttk.Radiobutton(row_mode, text=i18n.t("psd.mode.fit"), variable=self._mode_var, value="fit"); self._rb_fit.pack(side="left", padx=5)
        self._rb_fill = ttk.Radiobutton(row_mode, text=i18n.t("psd.mode.fill"), variable=self._mode_var, value="fill"); self._rb_fill.pack(side="left", padx=5)
        self._rb_orig = ttk.Radiobutton(row_mode, text=i18n.t("psd.mode.original"), variable=self._mode_var, value="original"); self._rb_orig.pack(side="left", padx=5)
        ttk.Label(main, text=i18n.t("psd.mode.hint"), foreground="gray").pack(anchor="w", pady=2)

        self._no_upscale_var = tk.BooleanVar(value=config.get("psd_no_upscale", False))
        self._cb_no_upscale = ttk.Checkbutton(main, text=i18n.t("psd.no.upscale"), variable=self._no_upscale_var); self._cb_no_upscale.pack(anchor="w", pady=2)
        self._clip_bounds_var = tk.BooleanVar(value=config.get("psd_clip_bounds", True))
        self._cb_clip_bounds = ttk.Checkbutton(main, text=i18n.t("psd.clip.bounds"), variable=self._clip_bounds_var); self._cb_clip_bounds.pack(anchor="w", pady=2)
        self._inherit_meta_var = tk.BooleanVar(value=config.get("psd_inherit_metadata", True))
        self._cb_inherit_meta = ttk.Checkbutton(main, text=i18n.t("psd.inherit.metadata"), variable=self._inherit_meta_var); self._cb_inherit_meta.pack(anchor="w", pady=2)

        ttk.Label(main, text=i18n.t("psd.section.batch")).pack(anchor="w", pady=(10, 2))
        row_in = ttk.Frame(main); row_in.pack(fill="x", pady=2)
        self._lbl_in = ttk.Label(row_in, text=i18n.t("psd.in.folder")); self._lbl_in.pack(side="left")
        self._in_var = tk.StringVar(value=config.get("psd_in_folder", ""))
        ttk.Entry(row_in, textvariable=self._in_var, width=30).pack(side="left", padx=5, fill="x", expand=True)
        self._btn_in = ttk.Button(row_in, text=i18n.t("common.browse"), command=self._browse_in); self._btn_in.pack(side="left")

        row_out = ttk.Frame(main); row_out.pack(fill="x", pady=2)
        self._lbl_out = ttk.Label(row_out, text=i18n.t("psd.out.folder")); self._lbl_out.pack(side="left")
        self._out_var = tk.StringVar(value=config.get("psd_out_folder", ""))
        ttk.Entry(row_out, textvariable=self._out_var, width=30).pack(side="left", padx=5, fill="x", expand=True)
        self._btn_out = ttk.Button(row_out, text=i18n.t("common.browse"), command=self._browse_out); self._btn_out.pack(side="left")

        row_batch = ttk.Frame(main); row_batch.pack(fill="x", pady=5)
        self._btn_batch = ttk.Button(row_batch, text=i18n.t("psd.batch"), command=self.batch_replace); self._btn_batch.pack(side="left", padx=5)
        self._btn_csv = ttk.Button(row_batch, text="Batch CSV", command=self.batch_csv_replace); self._btn_csv.pack(side="left", padx=5)

    def _browse_in(self):
        d = filedialog.askdirectory(title=i18n.t("psd.in.folder"))
        if d: self._in_var.set(d); config.set("psd_in_folder", d)

    def _browse_out(self):
        d = filedialog.askdirectory(title=i18n.t("psd.out.folder"))
        if d: self._out_var.set(d); config.set("psd_out_folder", d)

    def open_psd(self):
        path = filedialog.askopenfilename(title=i18n.t("psd.open"), filetypes=[("PSD", "*.psd"), ("All", "*.*")])
        if not path: return
        try:
            self._doc = self._ps.open(path)
            self._psd_path = Path(path)
            self._log(f"Opened: {self._psd_path.name}", "ok")
            self.scan_layers()
        except Exception as e:
            messagebox.showerror(i18n.t("error.title"), str(e))
            self._log(f"Open failed: {e}", "error")

    # ----- helpers -----
    def _read_doc_dpi(self) -> tuple[int, int]:
        """Читаем DPI открытого PSD, чтобы наследовать его в подготовленном файле."""
        try:
            r = float(self._doc.Resolution)  # px/inch (в PS одинаковый по X и Y)
            if r > 0:
                return (int(round(r)), int(round(r)))
        except Exception:
            pass
        return (72, 72)

    def scan_layers(self):
        if not self._doc:
            messagebox.showwarning(i18n.t("warning.title"), i18n.t("psd.no.doc"))
            return
        self._tree.delete(*self._tree.get_children())
        self._layers.clear()
        self._so_frames.clear()

        def walk(container, parent_id="", path=None):
            if path is None: path = []
            try: count = container.Layers.Count
            except Exception: return
            for i in range(1, count + 1):
                try:
                    layer = container.Layers.Item(i)
                    name = str(layer.Name)
                except Exception: continue
                new_path = path + [i]
                is_grp = _is_group(layer)
                is_so = _is_smart_object(layer) if not is_grp else False
                typ = "Group" if is_grp else ("SmartObject" if is_so else "Raster")
                node_id = self._tree.insert(parent_id, "end", text=name, values=(typ,))
                self._layers.append((name, new_path))
                if is_so:
                    try:
                        b = layer.Bounds
                        l, t, r, bot = float(b[0]), float(b[1]), float(b[2]), float(b[3])
                        self._so_frames[json.dumps(new_path)] = (l, t, r, bot)
                    except Exception: pass
                if is_grp: walk(layer, node_id, new_path)

        walk(self._doc)
        self._log(f"Scanned: {len(self._layers)} layers, {len(self._so_frames)} SO frames", "info")

    def unlock_all(self):
        if not self._doc: return
        try:
            jsx = """
(function() {
    function unlock(container) {
        for (var i = 0; i < container.layers.length; i++) {
            var L = container.layers[i];
            if (L.typename === "LayerSet") unlock(L);
            try { L.allLocked = false; } catch(_) {}
        }
    }
    unlock(app.activeDocument); return "OK";
})();
"""
            self._ps.app.DoJavaScript(jsx)
            self._log("All layers unlocked", "ok")
        except Exception as e:
            self._log(f"Unlock failed: {e}", "error")

    def unlock_layers(self):
        if not self._doc:
            messagebox.showwarning(i18n.t("warning.title"), i18n.t("psd.no.doc")); return
        try:
            self.unlock_all(); self.scan_layers()
            messagebox.showinfo(i18n.t("info.title"), "Все слои разблокированы")
        except Exception as e:
            messagebox.showerror(i18n.t("error.title"), str(e))
            self._log(f"Unlock failed: {e}", "error")

    # ----- SO size reading (JSX unchanged, работает нормально) -----
    def _read_so_true_size(self, so_layer=None) -> Optional[tuple[float, float]]:
        if so_layer is not None:
            try: self._doc.ActiveLayer = so_layer
            except Exception as e: self._log(f"SO activate failed: {e}", "warn")

        jsx = r"""
(function () {
    try {
        var ref = new ActionReference();
        ref.putEnumerated(charIDToTypeID("Lyr "), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
        var lyrDesc = executeActionGet(ref);
        if (!lyrDesc.hasKey(stringIDToTypeID("smartObject"))) return "ERR:not_smart_object";
        var soDesc = lyrDesc.getObjectValue(stringIDToTypeID("smartObject"));
        function d(x1,y1,x2,y2){var dx=x2-x1,dy=y2-y1;return Math.sqrt(dx*dx+dy*dy);}
        if (soDesc.hasKey(stringIDToTypeID("size"))) {
            var s = soDesc.getObjectValue(stringIDToTypeID("size"));
            try {
                var w3 = s.getUnitDoubleValue(stringIDToTypeID("width"));
                var h3 = s.getUnitDoubleValue(stringIDToTypeID("height"));
                if (w3 > 0 && h3 > 0) return w3.toFixed(3)+"|"+h3.toFixed(3)+"|size";
            } catch(_) {
                try {
                    var w4 = s.getDouble(stringIDToTypeID("width"));
                    var h4 = s.getDouble(stringIDToTypeID("height"));
                    if (w4 > 0 && h4 > 0) return w4.toFixed(3)+"|"+h4.toFixed(3)+"|size";
                } catch(__) {}
            }
        }
        if (soDesc.hasKey(stringIDToTypeID("link"))) {
            var linkDesc = soDesc.getObjectValue(stringIDToTypeID("link"));
            if (linkDesc.hasKey(stringIDToTypeID("size"))) {
                var linkSize = linkDesc.getObjectValue(stringIDToTypeID("size"));
                try {
                    var wLink = linkSize.getUnitDoubleValue(stringIDToTypeID("width"));
                    var hLink = linkSize.getUnitDoubleValue(stringIDToTypeID("height"));
                    if (wLink > 0 && hLink > 0) return wLink.toFixed(3)+"|"+hLink.toFixed(3)+"|link";
                } catch(_) {}
            }
        }
        if (soDesc.hasKey(stringIDToTypeID("transform"))) {
            var t = soDesc.getList(stringIDToTypeID("transform"));
            var w = d(t.getDouble(0),t.getDouble(1),t.getDouble(2),t.getDouble(3));
            var h = d(t.getDouble(0),t.getDouble(1),t.getDouble(6),t.getDouble(7));
            if (w > 0 && h > 0) return w.toFixed(3)+"|"+h.toFixed(3)+"|transform";
        }
        if (soDesc.hasKey(stringIDToTypeID("nonAffineTransform"))) {
            var n = soDesc.getList(stringIDToTypeID("nonAffineTransform"));
            var w2 = d(n.getDouble(0),n.getDouble(1),n.getDouble(2),n.getDouble(3));
            var h2 = d(n.getDouble(0),n.getDouble(1),n.getDouble(6),n.getDouble(7));
            if (w2 > 0 && h2 > 0) return w2.toFixed(3)+"|"+h2.toFixed(3)+"|nonAffine";
        }
        return "ERR:no_geometry";
    } catch (e) { return "ERR:"+e.message; }
})();
"""
        try:
            result = self._ps.app.DoJavaScript(jsx)
            raw = str(result).strip() if result is not None else ""
            if not raw or raw.startswith("ERR"):
                self._log(f"SO true-size JS: {raw or 'empty'}, fallback editContents", "warn")
                return self._read_so_size_via_edit_contents(so_layer)
            parts = raw.split("|")
            if len(parts) < 2: return None
            w = float(parts[0]); h = float(parts[1])
            src = parts[2] if len(parts) > 2 else "?"
            if w > 0 and h > 0:
                self._log(f"SO content size ({src}): {w:.0f}x{h:.0f}px", "info")
                return (w, h)
        except Exception as e:
            self._log(f"SO true-size read failed: {e}", "warn")
        return None

    def _read_so_size_via_edit_contents(self, so_layer) -> Optional[tuple[float, float]]:
        jsx = r"""
(function() {
    try {
        executeAction(stringIDToTypeID("placedLayerEditContents"),
                      new ActionDescriptor(), DialogModes.NO);
        var w = app.activeDocument.width.as('px');
        var h = app.activeDocument.height.as('px');
        app.activeDocument.close(SaveOptions.DONOTSAVECHANGES);
        return w + "|" + h;
    } catch(e) { return "ERR:" + e.message; }
})();
"""
        try:
            if so_layer: self._doc.ActiveLayer = so_layer
            result = str(self._ps.app.DoJavaScript(jsx)).strip()
            if not result.startswith("ERR"):
                parts = result.split("|")
                if len(parts) >= 2:
                    w = float(parts[0]); h = float(parts[1])
                    if w > 0 and h > 0:
                        self._log(f"SO size via editContents: {w:.0f}x{h:.0f}px", "ok")
                        return (w, h)
        except Exception as e:
            self._log(f"editContents exception: {e}", "error")
        return None

    # ----- Replacement -----
    def _replace_smart_object(self, so_layer, image_path: str, mode: str,
                              frame_key: Optional[str] = None,
                              isolate: bool = False) -> None:
        """Заменить содержимое SO с сохранением трансформации."""
        self._doc.ActiveLayer = so_layer

        # 1) Реальный внутренний размер SO
        fw = fh = 0
        ts = self._read_so_true_size(so_layer)
        if ts:
            fw, fh = int(round(ts[0])), int(round(ts[1]))
        else:
            es = self._read_so_size_via_edit_contents(so_layer)
            if es:
                fw, fh = int(round(es[0])), int(round(es[1]))
            else:
                stored = self._so_frames.get(frame_key) if frame_key else None
                if stored:
                    fl, ft, fr, fb = stored
                    fw, fh = int(round(fr - fl)), int(round(fb - ft))
                    self._log(f"WARN: using canvas bounds {fw}x{fh}", "error")
                else:
                    fw = fh = 1000

        # 2) Сравнение аспектов — самое важное для "почему не встаёт как оригинал"
        if PIL_AVAILABLE:
            try:
                _src = Image.open(image_path)
                sw, sh = _src.size
                src_ar = sw / sh if sh else 0
                tgt_ar = fw / fh if fh else 0
                diff = abs(src_ar - tgt_ar) / tgt_ar * 100 if tgt_ar else 0
                self._log(
                    f"Aspect: src {sw}x{sh} (AR={src_ar:.3f}) vs SO {fw}x{fh} (AR={tgt_ar:.3f}) — diff {diff:.1f}%",
                    "info",
                )
                if diff > 5:
                    self._log(
                        "Aspect mismatch -> в 'fill' будет crop, в 'fit' будут поля. "
                        "Выбирай fill чтобы фото стояло как оригинал.",
                        "warn",
                    )
            except Exception:
                pass

        # 3) Готовим файл под ТОЧНЫЙ размер fw×fh
        prepared_path = image_path
        if PIL_AVAILABLE and fw > 0 and fh > 0:
            ui_mode = (mode or self._mode_var.get() or "fill").lower()
            # 'original' трактуем как fill — мини-фото должно заполнить кадр
            if ui_mode == "original":
                ui_mode = "fill"
            if ui_mode == "fill":
                prepared_path = self._prepare_image_for_psd(
                    image_path, fw, fh, mode="fill", force_mode="fill", use_padding=False
                )
            else:
                prepared_path = self._prepare_image_for_psd(
                    image_path, fw, fh, mode="fit", use_padding=True
                )

        # 4) Собственно замена — placedLayerReplaceContents сохраняет матрицу трансформации SO
        self._run_so_replace_contents_jsx(prepared_path, "exact", "AUTO", isolate=isolate)

    def _run_so_replace_contents_jsx(self, image_path: str, fill_mode: str,
                                     frame: str, isolate: bool = False):
        norm = str(Path(image_path).resolve()).replace("\\", "/")
        jsx_template = r"""
(function () {
    try {
        var id = stringIDToTypeID("placedLayerReplaceContents");
        var desc = new ActionDescriptor();
        desc.putPath(charIDToTypeID("null"), new File("__IMAGE_PATH__"));
        desc.putInteger(charIDToTypeID("PgNm"), 1);
        executeAction(id, desc, DialogModes.NO);
        return "OK";
    } catch(e) { return "ERR:" + e.message; }
})();
"""
        jsx = jsx_template.replace("__IMAGE_PATH__", norm)
        try:
            result = str(self._ps.app.DoJavaScript(jsx))
            if result.startswith("ERR"):
                raise RuntimeError(result)
            self._log(f"SO content replaced: {Path(image_path).name}", "ok")
        except Exception as e:
            self._log(f"SO replace failed: {e}", "error")
            raise

    def _replace_raster_merge_down(self, layer, image_path: str, mode: str):
        try:
            b = layer.Bounds
            l, t, r, bot = float(b[0]), float(b[1]), float(b[2]), float(b[3])
            width = int(round(r - l)); height = int(round(bot - t))
        except Exception as e:
            self._log(f"Raster bounds read failed: {e}", "warn")
            l = t = 0; width = height = 500

        prepared_path = image_path
        if PIL_AVAILABLE and width > 0 and height > 0:
            prepared_path = self._prepare_image_for_psd(
                image_path, width, height, mode=mode, force_mode="fill", use_padding=False
            )

        self._doc.ActiveLayer = layer
        name = str(layer.Name)
        self._run_merge_down_jsx(prepared_path, l, t)
        self._log(f"Raster replaced (merge): {name}", "ok")

    def _run_merge_down_jsx(self, image_path: str, left: float, top: float):
        norm = str(Path(image_path).resolve()).replace("\\", "/")
        jsx = r"""
(function() {{
    try {{
        var f = new File("{image_path}");
        var desc1 = new ActionDescriptor();
        desc1.putPath(charIDToTypeID("null"), f);
        desc1.putEnumerated(charIDToTypeID("FTcs"), charIDToTypeID("QCSt"), charIDToTypeID("Qcsa"));
        var desc2 = new ActionDescriptor();
        desc2.putUnitDouble(charIDToTypeID("Hrzn"), charIDToTypeID("#Pxl"), {left});
        desc2.putUnitDouble(charIDToTypeID("Vrtc"), charIDToTypeID("#Pxl"), {top});
        desc1.putObject(charIDToTypeID("Ofst"), charIDToTypeID("Ofst"), desc2);
        executeAction(charIDToTypeID("Plc "), desc1, DialogModes.NO);
        executeAction(charIDToTypeID("Mrg2"), undefined, DialogModes.NO);
        return "OK";
    }} catch(e) {{ return "ERR:"+e.message; }}
}})();
""".format(image_path=norm, left=left, top=top)
        result = str(self._ps.app.DoJavaScript(jsx))
        if result.startswith("ERR"):
            raise RuntimeError(result)

    def _replace_layer_content(self, layer, image_path: str, mode: str,
                               frame_key: Optional[str] = None):
        if _is_smart_object(layer):
            self._replace_smart_object(layer, image_path, mode, frame_key=frame_key)
        else:
            self._replace_raster_merge_down(layer, image_path, mode)

    # ----- image prep (DPI-aware) -----
    def _prepare_image_for_psd(
        self,
        image_path: str,
        target_width: int,
        target_height: int,
        mode: str = "fill",
        force_mode: Optional[str] = None,
        use_padding: bool = False,
    ) -> str:
        out_dir = Path(self._psd_path).parent / "temp_prepared"
        out_dir.mkdir(exist_ok=True)
        stem = Path(image_path).stem
        out_path = out_dir / f"{stem}_prepared.png"

        effective_mode = force_mode if force_mode else mode
        no_upscale = self._no_upscale_var.get()
        if force_mode == "fill":
            no_upscale = False

        # DPI родительского PSD — критично для корректного masштаба в SO
        doc_dpi = self._read_doc_dpi()

        try:
            img = Image.open(image_path)

            sw, sh = img.size
            if min(sw, sh) < self._MIN_SOURCE_SIDE and not self._small_source_ack:
                ans = messagebox.askyesno(
                    "Маленький исходник",
                    f"Исходник {sw}x{sh}px слишком мал (рекомендуется >{self._MIN_SOURCE_SIDE}px).\n"
                    f"При масштабировании до {target_width}x{target_height}px качество снизится.\n\n"
                    f"Продолжить?",
                )
                if not ans:
                    raise RuntimeError("User cancelled due to small source")
                self._small_source_ack = True

            if use_padding:
                fitted = resize_with_mode(
                    img, target_width, target_height, mode="fit", no_upscale=no_upscale
                )
                if fitted.mode != "RGBA":
                    fitted = fitted.convert("RGBA")
                canvas = Image.new("RGBA", (target_width, target_height), (0, 0, 0, 0))
                off_x = (target_width - fitted.size[0]) // 2
                off_y = (target_height - fitted.size[1]) // 2
                canvas.paste(fitted, (off_x, off_y), fitted)
                result_img = canvas
            else:
                result_img = resize_with_mode(
                    img, target_width, target_height, mode=effective_mode, no_upscale=no_upscale
                )

            # МЯГКИЙ шарп только если реально сильный upscale (>1.5x)
            try:
                orig_w, orig_h = img.size
                scale = max(target_width / orig_w, target_height / orig_h) if effective_mode in ("fill", "cover") \
                    else min(target_width / orig_w, target_height / orig_h)
                if scale > 1.5 and not no_upscale:
                    result_img = result_img.filter(
                        ImageFilter.UnsharpMask(radius=1.0, percent=60, threshold=3)
                    )
                    self._log(f"Mild sharpen applied (upscale x{scale:.2f})", "info")
            except Exception:
                pass

            # НАСЛЕДУЕМ DPI родительского PSD — иначе Photoshop пересчитает размер при вставке
            result_img.info["dpi"] = doc_dpi
            result_img.save(str(out_path), dpi=doc_dpi)
            self._log(
                f"Prepared: {out_path.name} ({result_img.size[0]}x{result_img.size[1]}px @ {doc_dpi[0]}dpi)",
                "ok",
            )
            return str(out_path)

        except Exception as e:
            self._log(f"Image prepare failed: {e}", "error")
            return image_path

    # ----- Actions -----
    def replace_selected(self):
        if not self._doc:
            messagebox.showwarning(i18n.t("warning.title"), i18n.t("psd.no.doc")); return
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning(i18n.t("warning.title"), "No layer selected"); return
        idx = self._tree.index(sel[0])
        if idx >= len(self._layers): return
        name, path = self._layers[idx]
        layer = self._resolve_layer(path)

        image_path = filedialog.askopenfilename(
            title="Select image",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.tif *.tiff *.bmp"), ("All", "*.*")],
        )
        if not image_path: return

        try:
            mode = self._mode_var.get()
            config.set("psd_mode", mode)
            config.set("psd_no_upscale", self._no_upscale_var.get())
            frame_key = json.dumps(path)
            self._replace_layer_content(layer, image_path, mode, frame_key=frame_key)
            self._log(f"Replaced: {name}", "ok")
        except Exception as e:
            messagebox.showerror(i18n.t("error.title"), str(e))
            self._log(f"Replace failed: {e}", "error")

    def _resolve_layer(self, path: list):
        obj = self._doc
        for idx in path:
            obj = obj.Layers.Item(idx)
        return obj

    def _find_layer_by_name(self, target_name: str):
        target_lower = target_name.lower()
        for name, path in self._layers:
            if name.lower() == target_lower:
                return (name, path)
        return None

    def _find_photo_layer(self):
        for name, path in self._layers:
            if name.lower() in self._PHOTO_SO_NAMES:
                layer = self._resolve_layer(path)
                if _is_smart_object(layer):
                    return (name, path)
        for name, path in self._layers:
            nl = name.lower()
            if any(kw in nl for kw in self._PHOTO_KEYWORDS):
                layer = self._resolve_layer(path)
                if not _is_smart_object(layer) and not _is_group(layer):
                    return (name, path)
        largest = None; largest_area = 0
        for name, path in self._layers:
            key = json.dumps(path)
            if key in self._so_frames:
                l, t, r, b = self._so_frames[key]
                area = (r - l) * (b - t)
                if area > largest_area:
                    largest_area = area; largest = (name, path)
        return largest

    def auto_replace_photo(self):
        if not self._doc:
            messagebox.showwarning(i18n.t("warning.title"), i18n.t("psd.no.doc")); return
        found = self._find_photo_layer()
        if not found:
            messagebox.showinfo(i18n.t("info.title"), "Photo layer not found"); return
        name, path = found
        self._log(f"Auto-detected: {name}", "info")
        image_path = filedialog.askopenfilename(
            title="Select photo",
            filetypes=[("Images", "*.jpg *.jpeg *.png"), ("All", "*.*")],
        )
        if not image_path: return
        try:
            layer = self._resolve_layer(path)
            mode = self._mode_var.get()
            frame_key = json.dumps(path)
            self._replace_layer_content(layer, image_path, mode, frame_key=frame_key)
            self._log(f"Auto-replaced: {name}", "ok")
        except Exception as e:
            messagebox.showerror(i18n.t("error.title"), str(e))
            self._log(f"Auto-replace failed: {e}", "error")

    def pick_so_and_replace(self):
        if not self._doc or not self._psd_path:
            messagebox.showwarning(i18n.t("warning.title"), i18n.t("psd.no.doc")); return
        so_layers = []
        for name, path in self._layers:
            layer = self._resolve_layer(path)
            if _is_smart_object(layer):
                bounds = self._so_frames.get(json.dumps(path), (0, 0, 100, 100))
                so_layers.append((name, path, bounds))
        if not so_layers:
            messagebox.showinfo(i18n.t("info.title"), "No Smart Objects found"); return

        def on_replace(name: str, path_key: list, img_path: str):
            try:
                layer = self._resolve_layer(path_key)
                mode = self._mode_var.get()
                self._replace_smart_object(
                    layer, img_path, mode, frame_key=json.dumps(path_key), isolate=True
                )
                self._log(f"SO replaced: {name}", "ok")
            except Exception as e:
                messagebox.showerror(i18n.t("error.title"), str(e))
                self._log(f"SO replace failed: {e}", "error")

        SOPickerWindow(self.winfo_toplevel(), so_layers, self._psd_path, on_replace)

    def replace_all_photo_so(self):
        if not self._doc:
            messagebox.showwarning(i18n.t("warning.title"), i18n.t("psd.no.doc")); return
        image_path = filedialog.askopenfilename(
            title="Select photo for all SO",
            filetypes=[("Images", "*.jpg *.jpeg *.png"), ("All", "*.*")],
        )
        if not image_path: return
        matched = []
        for name, path in self._layers:
            if name.lower() in self._PHOTO_SO_NAMES:
                layer = self._resolve_layer(path)
                if _is_smart_object(layer):
                    matched.append((name, path, layer))
        if not matched:
            messagebox.showinfo(i18n.t("info.title"), "No matching photo SO found"); return
        try:
            mode = self._mode_var.get()
            for name, path, layer in matched:
                self._replace_smart_object(
                    layer, image_path, mode, frame_key=json.dumps(path)
                )
                self._log(f"Replaced SO: {name}", "ok")
            messagebox.showinfo(i18n.t("info.title"), f"Replaced {len(matched)} SO layers")
        except Exception as e:
            messagebox.showerror(i18n.t("error.title"), str(e))
            self._log(f"Batch SO replace failed: {e}", "error")

    def batch_replace(self):
        in_folder = self._in_var.get(); out_folder = self._out_var.get()
        if not in_folder or not out_folder:
            messagebox.showwarning(i18n.t("warning.title"), "Set input/output folders"); return
        in_dir = Path(in_folder); out_dir = Path(out_folder)
        if not in_dir.exists():
            messagebox.showerror(i18n.t("error.title"), f"Input folder not found: {in_dir}"); return
        out_dir.mkdir(parents=True, exist_ok=True)
        images = list(in_dir.glob("*.jpg")) + list(in_dir.glob("*.png"))
        if not images:
            messagebox.showinfo(i18n.t("info.title"), "No images in input folder"); return
        if not self._psd_path:
            messagebox.showwarning(i18n.t("warning.title"), "Open template PSD first"); return
        template_path = str(self._psd_path)
        found = self._find_photo_layer()
        if not found:
            messagebox.showinfo(i18n.t("info.title"), "Photo layer not found in template"); return
        layer_name, layer_path = found
        self._log(f"Batch target layer: {layer_name}", "info")
        mode = self._mode_var.get(); success = 0
        for img_path in images:
            stem = img_path.stem
            try:
                if success > 0:
                    try: self._doc.Close(2)
                    except Exception: pass
                    self._doc = self._ps.open(template_path); self.scan_layers()
                layer = self._resolve_layer(layer_path)
                self._replace_layer_content(layer, str(img_path), mode, frame_key=json.dumps(layer_path))
                out_path = out_dir / f"{stem}.psd"
                self._doc.SaveAs(str(out_path))
                self._log(f"Saved: {out_path.name}", "ok"); success += 1
            except Exception as e:
                self._log(f"Batch failed for {stem}: {e}", "error")
        messagebox.showinfo(i18n.t("info.title"), f"Batch: {success}/{len(images)} saved to {out_dir}")

    def batch_csv_replace(self):
        csv_path = filedialog.askopenfilename(title="Select CSV", filetypes=[("CSV", "*.csv"), ("All", "*.*")])
        if not csv_path: return
        out_folder = self._out_var.get()
        if not out_folder:
            messagebox.showwarning(i18n.t("warning.title"), "Set output folder"); return
        out_dir = Path(out_folder); out_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                rows_raw = list(csv.DictReader(f))
        except Exception as e:
            messagebox.showerror(i18n.t("error.title"), f"CSV read failed: {e}"); return
        if not rows_raw:
            messagebox.showinfo(i18n.t("info.title"), "CSV is empty"); return
        layer_columns = [c for c in rows_raw[0].keys() if c != "output_name"]
        if not layer_columns:
            messagebox.showerror(i18n.t("error.title"), "CSV must have layer columns"); return
        rows = []
        for r in rows_raw:
            out_name = r.get("output_name", "").strip()
            if not out_name: continue
            photos = {c: Path(r[c].strip()) for c in layer_columns if r.get(c, "").strip()}
            if photos: rows.append({"output_name": out_name, "photos": photos})
        if not rows:
            messagebox.showinfo(i18n.t("info.title"), "No valid rows in CSV"); return
        if not self._psd_path:
            messagebox.showwarning(i18n.t("warning.title"), "Open template PSD first"); return
        self._log(f"CSV batch: {len(rows)} variant(s), {len(layer_columns)} layer(s)", "info")
        template_path = str(self._psd_path); success = 0
        for idx, row in enumerate(rows, start=1):
            out_name = row["output_name"]; photos = row["photos"]
            try:
                if idx > 1:
                    try: self._doc.Close(2)
                    except Exception: pass
                    self._doc = self._ps.open(template_path); self.scan_layers()
                for layer_name, photo_path in photos.items():
                    found = self._find_layer_by_name(layer_name)
                    if not found:
                        self._log(f"[{out_name}] layer '{layer_name}' not found — skip", "warn"); continue
                    _n, path = found
                    layer = self._resolve_layer(path)
                    self._replace_layer_content(
                        layer, str(photo_path), self._mode_var.get(),
                        frame_key=json.dumps(path),
                    )
                    self._log(f"[{out_name}] '{layer_name}' <- {photo_path.name}", "ok")
                target = out_dir / f"{out_name}.psd"
                self._doc.SaveAs(str(target))
                self._log(f"Saved: {target.name}", "ok"); success += 1
            except Exception as exc:
                self._log(f"[{out_name}] FAILED: {exc}", "error")
        self._log(f"CSV batch complete: {success}/{len(rows)} saved to {out_dir}", "ok")
        messagebox.showinfo(i18n.t("info.title"), f"Done: {success}/{len(rows)} PSD saved to:\n{out_dir}")

    def _retranslate(self) -> None:
        pairs = [
            (self._btn_open, "psd.open"), (self._btn_scan, "psd.scan"),
            (self._btn_unlck, "psd.unlock"), (self._btn_repl, "psd.replace"),
            (self._btn_batch, "psd.batch"), (self._btn_in, "common.browse"),
            (self._btn_out, "common.browse"),
            (self._rb_fit, "psd.mode.fit"), (self._rb_fill, "psd.mode.fill"),
            (self._rb_orig, "psd.mode.original"),
            (self._cb_no_upscale, "psd.no.upscale"),
            (self._cb_clip_bounds, "psd.clip.bounds"),
            (self._cb_inherit_meta, "psd.inherit.metadata"),
        ]
        for widget, key in pairs:
            widget.configure(text=i18n.t(key))
        self._btn_auto.configure(text="Авто фото")
        self._btn_picker.configure(text="Выбор SO")
        self._btn_all_so.configure(text="Во все SO")
        self._btn_csv.configure(text="Batch CSV")
        self._lbl_in.configure(text=i18n.t("psd.in.folder"))
        self._lbl_out.configure(text=i18n.t("psd.out.folder"))
        if self._ps and not self._ps.available:
            self._warn.configure(text=f"{i18n.t('psd.no.photoshop')} ({self._ps.error()})")


PsdToolsFrameCTk = PsdToolsFrame
