"""PSD Tools Tab - профессиональный CustomTkinter UI с Photoshop COM."""

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

# ===== Импорт модуля умной подмены =====
from modules.image_replace import resize_with_mode, prepare_for_smart_object
from modules.so_picker import SOPickerWindow

try:
    from PIL import Image, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ========================================

LogFn = Callable[[str, str], None]


def _is_windows() -> bool:
    return sys.platform.startswith("win")


# ---------------------------------------------------------------------------
# Layer-type helpers
# ---------------------------------------------------------------------------

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
    """LayerKind.SMARTOBJECT = 17."""
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
    """Wrapper around Photoshop COM."""

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
    # Ключевые слова для автопоиска слоя с фото
    _PHOTO_KEYWORDS = (
        "photo edit", "photo", "фото", "foto", "portrait", "портрет",
        "avatar", "аватар", "headshot", "image edit", "image",
        "снимок", "picture", "pic", "user photo", "your photo",
    )

    # Имена смарт-объектов, куда подставляется ОДНО и то же фото
    _PHOTO_SO_NAMES = ("photo edit", "наложение", "edit small photo")

    # Порог: если min(sw, sh) < этого значения — спросить у юзера подтверждение
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

    def _build(self) -> None:
        main = ttk.Frame(self, padding=10)
        main.pack(fill="both", expand=True)

        if self._ps and not self._ps.available:
            self._warn = ttk.Label(main, text=f"{i18n.t('psd.no.photoshop')}", foreground="red")
            self._warn.pack(pady=10)
        else:
            self._warn = None

        # Open/Scan/Unlock
        row0 = ttk.Frame(main)
        row0.pack(fill="x", pady=5)
        self._btn_open = ttk.Button(row0, text=i18n.t("psd.open"), command=self.open_psd)
        self._btn_open.pack(side="left", padx=5)
        self._btn_scan = ttk.Button(row0, text=i18n.t("psd.scan"), command=self.scan_layers)
        self._btn_scan.pack(side="left", padx=5)
        self._btn_unlck = ttk.Button(row0, text=i18n.t("psd.unlock"), command=self.unlock_layers)
        self._btn_unlck.pack(side="left", padx=5)

        # Layers list
        ttk.Label(main, text=i18n.t("psd.section.layers")).pack(anchor="w", pady=(10, 2))
        frame_list = ttk.Frame(main)
        frame_list.pack(fill="both", expand=True)
        sb = ttk.Scrollbar(frame_list, orient="vertical")
        sb.pack(side="right", fill="y")
        self._tree = ttk.Treeview(frame_list, columns=("type",), show="tree headings", yscrollcommand=sb.set)
        self._tree.heading("#0", text="Layer")
        self._tree.heading("type", text="Type")
        self._tree.column("type", width=80)
        self._tree.pack(side="left", fill="both", expand=True)
        sb.config(command=self._tree.yview)

        # Actions
        ttk.Label(main, text=i18n.t("psd.section.actions")).pack(anchor="w", pady=(10, 2))
        row_act = ttk.Frame(main)
        row_act.pack(fill="x", pady=5)

        self._btn_repl = ttk.Button(row_act, text=i18n.t("psd.replace"), command=self.replace_selected)
        self._btn_repl.pack(side="left", padx=5)

        self._btn_auto = ttk.Button(row_act, text="Авто фото", command=self.auto_replace_photo)
        self._btn_auto.pack(side="left", padx=5)

        self._btn_picker = ttk.Button(row_act, text="Выбор SO", command=self.pick_so_and_replace)
        self._btn_picker.pack(side="left", padx=5)

        self._btn_all_so = ttk.Button(row_act, text="Во все SO", command=self.replace_all_photo_so)
        self._btn_all_so.pack(side="left", padx=5)

        # Mode
        ttk.Label(main, text=i18n.t("psd.mode")).pack(anchor="w", pady=(10, 2))
        self._mode_var = tk.StringVar(value=config.get("psd_mode", "fill"))
        row_mode = ttk.Frame(main)
        row_mode.pack(fill="x")
        self._rb_fit = ttk.Radiobutton(row_mode, text=i18n.t("psd.mode.fit"), variable=self._mode_var, value="fit")
        self._rb_fit.pack(side="left", padx=5)
        self._rb_fill = ttk.Radiobutton(row_mode, text=i18n.t("psd.mode.fill"), variable=self._mode_var, value="fill")
        self._rb_fill.pack(side="left", padx=5)
        self._rb_orig = ttk.Radiobutton(row_mode, text=i18n.t("psd.mode.original"), variable=self._mode_var, value="original")
        self._rb_orig.pack(side="left", padx=5)

        ttk.Label(main, text=i18n.t("psd.mode.hint"), foreground="gray").pack(anchor="w", pady=2)

        self._no_upscale_var = tk.BooleanVar(value=config.get("psd_no_upscale", False))
        self._cb_no_upscale = ttk.Checkbutton(main, text=i18n.t("psd.no.upscale"), variable=self._no_upscale_var)
        self._cb_no_upscale.pack(anchor="w", pady=2)

        self._clip_bounds_var = tk.BooleanVar(value=config.get("psd_clip_bounds", True))
        self._cb_clip_bounds = ttk.Checkbutton(main, text=i18n.t("psd.clip.bounds"), variable=self._clip_bounds_var)
        self._cb_clip_bounds.pack(anchor="w", pady=2)

        self._inherit_meta_var = tk.BooleanVar(value=config.get("psd_inherit_metadata", True))
        self._cb_inherit_meta = ttk.Checkbutton(main, text=i18n.t("psd.inherit.metadata"), variable=self._inherit_meta_var)
        self._cb_inherit_meta.pack(anchor="w", pady=2)

        # Batch
        ttk.Label(main, text=i18n.t("psd.section.batch")).pack(anchor="w", pady=(10, 2))

        row_in = ttk.Frame(main)
        row_in.pack(fill="x", pady=2)
        self._lbl_in = ttk.Label(row_in, text=i18n.t("psd.in.folder"))
        self._lbl_in.pack(side="left")
        self._in_var = tk.StringVar(value=config.get("psd_in_folder", ""))
        ttk.Entry(row_in, textvariable=self._in_var, width=30).pack(side="left", padx=5, fill="x", expand=True)
        self._btn_in = ttk.Button(row_in, text=i18n.t("common.browse"), command=self._browse_in)
        self._btn_in.pack(side="left")

        row_out = ttk.Frame(main)
        row_out.pack(fill="x", pady=2)
        self._lbl_out = ttk.Label(row_out, text=i18n.t("psd.out.folder"))
        self._lbl_out.pack(side="left")
        self._out_var = tk.StringVar(value=config.get("psd_out_folder", ""))
        ttk.Entry(row_out, textvariable=self._out_var, width=30).pack(side="left", padx=5, fill="x", expand=True)
        self._btn_out = ttk.Button(row_out, text=i18n.t("common.browse"), command=self._browse_out)
        self._btn_out.pack(side="left")

        row_batch = ttk.Frame(main)
        row_batch.pack(fill="x", pady=5)
        self._btn_batch = ttk.Button(row_batch, text=i18n.t("psd.batch"), command=self.batch_replace)
        self._btn_batch.pack(side="left", padx=5)

        self._btn_csv = ttk.Button(row_batch, text="Batch CSV", command=self.batch_csv_replace)
        self._btn_csv.pack(side="left", padx=5)

    def _browse_in(self):
        d = filedialog.askdirectory(title=i18n.t("psd.in.folder"))
        if d:
            self._in_var.set(d)
            config.set("psd_in_folder", d)

    def _browse_out(self):
        d = filedialog.askdirectory(title=i18n.t("psd.out.folder"))
        if d:
            self._out_var.set(d)
            config.set("psd_out_folder", d)

    def open_psd(self):
        path = filedialog.askopenfilename(title=i18n.t("psd.open"), filetypes=[("PSD", "*.psd"), ("All", "*.*")])
        if not path:
            return
        try:
            self._doc = self._ps.open(path)
            self._psd_path = Path(path)
            self._log(f"Opened: {self._psd_path.name}", "ok")
            self.scan_layers()
        except Exception as e:
            messagebox.showerror(i18n.t("error.title"), str(e))
            self._log(f"Open failed: {e}", "error")

    def scan_layers(self):
        if not self._doc:
            messagebox.showwarning(i18n.t("warning.title"), i18n.t("psd.no.doc"))
            return
        self._tree.delete(*self._tree.get_children())
        self._layers.clear()
        self._so_frames.clear()

        def walk(container, parent_id="", path=None):
            if path is None:
                path = []
            try:
                count = container.Layers.Count
            except Exception:
                return
            for i in range(1, count + 1):
                try:
                    layer = container.Layers.Item(i)
                    name = str(layer.Name)
                except Exception:
                    continue

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
                        key = json.dumps(new_path)
                        self._so_frames[key] = (l, t, r, bot)
                    except Exception:
                        pass

                if is_grp:
                    walk(layer, node_id, new_path)

        walk(self._doc)
        self._log(f"Scanned: {len(self._layers)} layers, {len(self._so_frames)} SO frames", "info")

    def unlock_all(self):
        if not self._doc:
            return
        try:
            jsx = """
(function() {
    function unlock(container) {
        for (var i = 0; i < container.layers.length; i++) {
            var L = container.layers[i];
            if (L.typename === "LayerSet") {
                unlock(L);
            }
            try { L.allLocked = false; } catch(_) {}
        }
    }
    unlock(app.activeDocument);
    return "OK";
})();
"""
            self._ps.app.DoJavaScript(jsx)
            self._log("All layers unlocked", "ok")
        except Exception as e:
            self._log(f"Unlock failed: {e}", "error")

    def _read_so_true_size(self, so_layer=None) -> Optional[tuple[float, float]]:
        """
        Читает НАТИВНЫЙ размер вложенного контента SO (ключ "size").
        Fallback 1: transform/nonAffine (размер на холсте)
        Fallback 2: editContents
        """
        if so_layer is not None:
            try:
                self._doc.ActiveLayer = so_layer
            except Exception as e:
                self._log(f"SO activate before size-read failed: {e}", "warn")

        jsx = r"""
(function () {
    try {
        var ref = new ActionReference();
        ref.putEnumerated(charIDToTypeID("Lyr "),
                         charIDToTypeID("Ordn"),
                         charIDToTypeID("Trgt"));
        var lyrDesc = executeActionGet(ref);

        if (!lyrDesc.hasKey(stringIDToTypeID("smartObject"))) {
            return "ERR:not_smart_object";
        }
        var soDesc = lyrDesc.getObjectValue(stringIDToTypeID("smartObject"));
        function d(x1,y1,x2,y2){var dx=x2-x1,dy=y2-y1;return Math.sqrt(dx*dx+dy*dy);}

        // 1) НАТИВНЫЙ размер контента (приоритет!)
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

        // проверка через link (embedded/linked content)
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

        // 2) fallback: размер на холсте
        if (soDesc.hasKey(stringIDToTypeID("transform"))) {
            var t = soDesc.getList(stringIDToTypeID("transform"));
            var w = d(t.getDouble(0), t.getDouble(1), t.getDouble(2), t.getDouble(3));
            var h = d(t.getDouble(0), t.getDouble(1), t.getDouble(6), t.getDouble(7));
            if (w > 0 && h > 0) return w.toFixed(3)+"|"+h.toFixed(3)+"|transform";
        }
        if (soDesc.hasKey(stringIDToTypeID("nonAffineTransform"))) {
            var n = soDesc.getList(stringIDToTypeID("nonAffineTransform"));
            var w2 = d(n.getDouble(0), n.getDouble(1), n.getDouble(2), n.getDouble(3));
            var h2 = d(n.getDouble(0), n.getDouble(1), n.getDouble(6), n.getDouble(7));
            if (w2 > 0 && h2 > 0) return w2.toFixed(3)+"|"+h2.toFixed(3)+"|nonAffine";
        }
        return "ERR:no_geometry";
    } catch (e) { return "ERR:"+e.message; }
})();
"""
        try:
            result = self._ps.app.DoJavaScript(jsx)
            raw = str(result).strip() if result is not None else ""
            self._log(f"[DEBUG] JS true_size raw result: '{raw}'", "info")
            if not raw or raw.startswith("ERR"):
                self._log(f"⚠ SO true-size JS failed: {raw or 'empty'}, trying editContents", "warn")
                return self._read_so_size_via_edit_contents(so_layer)
            parts = raw.split("|")
            if len(parts) < 2:
                return None
            w = float(parts[0]); h = float(parts[1])
            src = parts[2] if len(parts) > 2 else "?"
            if w > 0 and h > 0:
                self._log(f"✅ SO content size source: {src} ({w:.0f}x{h:.0f}px)", "info")
                return (w, h)
        except Exception as e:
            self._log(f"SO true-size read failed: {e}", "warn")
        return None

    def _read_so_size_via_edit_contents(self, so_layer) -> Optional[tuple[float, float]]:
        """
        Fallback для edge cases.
        Открывает SO и читает точный размер контента через document dimensions.
        """
        jsx = r"""
(function() {
    try {
        executeAction(stringIDToTypeID("placedLayerEditContents"), 
                     new ActionDescriptor(), DialogModes.NO);
        var w = app.activeDocument.width.as('px');
        var h = app.activeDocument.height.as('px');
        app.activeDocument.close(SaveOptions.DONOTSAVECHANGES);
        return w + "|" + h;
    } catch(e) {
        return "ERR:" + e.message;
    }
})();
"""
        try:
            if so_layer:
                self._doc.ActiveLayer = so_layer
            result = self._ps.app.DoJavaScript(jsx)
            
            raw_result = str(result).strip()
            self._log(f"[DEBUG] editContents raw result: '{raw_result}'", "info")
            
            if not raw_result.startswith("ERR"):
                parts = raw_result.split("|")
                if len(parts) >= 2:
                    try:
                        w = float(parts[0])
                        h = float(parts[1])
                        if w > 0 and h > 0:
                            self._log(f"✅ SO size via editContents: {w:.0f}x{h:.0f}px", "ok")
                            return (w, h)
                        else:
                            self._log(f"⚠ editContents returned invalid dimensions: {w}x{h}", "warn")
                    except (ValueError, IndexError) as e:
                        self._log(f"⚠ editContents parse error: {e}", "warn")
                else:
                    self._log(f"⚠ editContents returned invalid format: '{raw_result}'", "warn")
            else:
                self._log(f"⚠ editContents returned error: {raw_result}", "warn")
                
        except Exception as e:
            self._log(f"❌ Edit contents exception: {type(e).__name__}: {e}", "error")
            try:
                import traceback
                self._log(f"Traceback: {traceback.format_exc()}", "error")
            except:
                pass
                
        return None

    def _replace_smart_object(self, so_layer, image_path: str, mode: str,
                              frame_key: Optional[str] = None,
                              isolate: bool = False) -> None:
        """Заменить содержимое Smart Object с сохранением трансформаций"""
        self._doc.ActiveLayer = so_layer

        fw = fh = 0
        true_size = self._read_so_true_size(so_layer)
        if true_size:
            fw = int(round(true_size[0]))
            fh = int(round(true_size[1]))
            self._log(f"✅ SO content frame: {fw}x{fh}px", "info")
        else:
            # Пробуем editContents как более точный fallback
            self._log(f"⚠ JS true_size failed, trying editContents fallback", "warn")
            edit_size = self._read_so_size_via_edit_contents(so_layer)
            
            if edit_size and edit_size[0] > 0 and edit_size[1] > 0:
                fw = int(round(edit_size[0]))
                fh = int(round(edit_size[1]))
                self._log(f"✅ SO embedded size: {fw}x{fh}px (via editContents)", "ok")
            else:
                # Последний fallback - bounds (НЕ РЕКОМЕНДУЕТСЯ для замены!)
                self._log(f"⚠⚠ All SO size detection failed, using canvas bounds", "error")
                try:
                    stored_frame = self._so_frames.get(frame_key) if frame_key else None
                    if stored_frame:
                        fl, ft, fr, fb = stored_frame
                    else:
                        b = so_layer.Bounds
                        fl = float(b[0]); ft = float(b[1])
                        fr = float(b[2]); fb = float(b[3])
                    fw = int(round(fr - fl))
                    fh = int(round(fb - ft))
                    self._log(f"⚠⚠⚠ Using canvas bounds: {fw}x{fh}px - РЕЗУЛЬТАТ МОЖЕТ БЫТЬ НЕТОЧНЫМ!", "error")
                    
                    # Показываем предупреждение пользователю
                    try:
                        messagebox.showwarning(
                            "Внимание",
                            f"Не удалось определить точный размер Smart Object.\n\n"
                            f"Используется размер на канвасе: {fw}x{fh}px\n"
                            f"Результат может быть искажён.\n\n"
                            f"Рекомендация: пересохраните PSD."
                        )
                    except:
                        pass
                except Exception as e:
                    self._log(f"❌ SO bounds read failed: {e}", "error")
                    fw = fh = 1000  # Default fallback

        # Заменяем фото ИДЕНТИЧНО оригиналу: режим FILL БЕЗ padding
        prepared_path = image_path
        if PIL_AVAILABLE and fw > 0 and fh > 0:
            prepared_path = self._prepare_image_for_psd(
                image_path, fw, fh, mode="fill", force_mode="fill", use_padding=False
            )

        stored = self._so_frames.get(frame_key) if frame_key else None
        frame_literal = ",".join(f"{v:.3f}" for v in stored) if stored else "AUTO"

        returned = self._run_so_replace_contents_jsx(
            prepared_path, "exact", frame_literal, isolate=isolate,
        )
        if frame_key and returned:
            self._so_frames[frame_key] = returned

    def _run_so_replace_contents_jsx(
        self, image_path: str, fill_mode: str, frame: str, isolate: bool = False
    ):
        """
        Замена контента SO через placedLayerReplaceContents.
        isolate=True: не затрагивает связанные копии (использует unique ID).
        """
        norm = str(Path(image_path).resolve()).replace("\\", "/")

        jsx_template = r"""
(function() {{
    try {{
        var idplacedLayerReplaceContents = stringIDToTypeID("placedLayerReplaceContents");
        var desc = new ActionDescriptor();
        desc.putPath(charIDToTypeID("null"), new File("{image_path}"));
        desc.putEnumerated(charIDToTypeID("FTcs"), charIDToTypeID("QCSt"),
                          stringIDToTypeID("{fill_mode}"));
        executeAction(idplacedLayerReplaceContents, desc, DialogModes.NO);
        return "OK";
    }} catch(e) {{
        return "ERR:"+e.message;
    }}
}})();
"""
        jsx = jsx_template.format(image_path=norm, fill_mode=fill_mode)

        try:
            result = str(self._ps.app.DoJavaScript(jsx))
            if result.startswith("ERR"):
                raise RuntimeError(result)
            self._log(f"SO content replaced: {Path(image_path).name}", "ok")
            return None
        except Exception as e:
            self._log(f"SO replace failed: {e}", "error")
            raise

    def _replace_raster_merge_down(self, layer, image_path: str, mode: str):
        """Замена для растровых слоев: Place → Merge Down"""
        try:
            b = layer.Bounds
            l, t, r, bot = float(b[0]), float(b[1]), float(b[2]), float(b[3])
            width = int(round(r - l))
            height = int(round(bot - t))
        except Exception as e:
            self._log(f"Raster bounds read failed: {e}", "warn")
            width = height = 500

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
        """Place image → Merge Down"""
        norm = str(Path(image_path).resolve()).replace("\\", "/")
        jsx = r"""
(function() {{
    try {{
        var f = new File("{image_path}");
        var desc1 = new ActionDescriptor();
        desc1.putPath(charIDToTypeID("null"), f);
        desc1.putEnumerated(charIDToTypeID("FTcs"), charIDToTypeID("QCSt"),
                           charIDToTypeID("Qcsa"));
        var desc2 = new ActionDescriptor();
        desc2.putUnitDouble(charIDToTypeID("Hrzn"), charIDToTypeID("#Pxl"), {left});
        desc2.putUnitDouble(charIDToTypeID("Vrtc"), charIDToTypeID("#Pxl"), {top});
        desc1.putObject(charIDToTypeID("Ofst"), charIDToTypeID("Ofst"), desc2);
        executeAction(charIDToTypeID("Plc "), desc1, DialogModes.NO);

        executeAction(charIDToTypeID("Mrg2"), undefined, DialogModes.NO);
        return "OK";
    }} catch(e) {{
        return "ERR:"+e.message;
    }}
}})();
""".format(image_path=norm, left=left, top=top)

        result = str(self._ps.app.DoJavaScript(jsx))
        if result.startswith("ERR"):
            raise RuntimeError(result)

    def _replace_layer_content(self, layer, image_path: str, mode: str, frame_key: Optional[str] = None):
        """Dispatcher: SO или raster"""
        if _is_smart_object(layer):
            self._replace_smart_object(layer, image_path, mode, frame_key=frame_key)
        else:
            self._replace_raster_merge_down(layer, image_path, mode)

    def _prepare_image_for_psd(
        self,
        image_path: str,
        target_width: int,
        target_height: int,
        mode: str = "fill",
        force_mode: Optional[str] = None,
        use_padding: bool = False,
    ) -> str:
        """Подготовка изображения: resize, padding, save"""
        from modules.image_replace import prepare_image_for_psd

        out_dir = Path(self._psd_path).parent / "temp_prepared"
        out_dir.mkdir(exist_ok=True)

        stem = Path(image_path).stem
        out_path = out_dir / f"{stem}_prepared.png"

        effective_mode = force_mode if force_mode else mode
        no_upscale = self._no_upscale_var.get()

        # Для SO с force_fill игнорируем no_upscale
        if force_mode == "fill":
            no_upscale = False

        try:
            from PIL import Image
            img = Image.open(image_path)
            
            # Проверка размера исходника
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

            # Resize
            if use_padding:
                result_img = prepare_for_smart_object(img, target_width, target_height)
            else:
                result_img = resize_with_mode(
                    img, target_width, target_height, mode=effective_mode, no_upscale=no_upscale
                )

            # Save
            result_img.save(str(out_path))
            self._log(f"✅ Saved prepared: {out_path.name} ({result_img.size[0]}x{result_img.size[1]}px)", "ok")
            return str(out_path)

        except Exception as e:
            self._log(f"Image prepare failed: {e}", "error")
            return image_path

    def replace_selected(self):
        if not self._doc:
            messagebox.showwarning(i18n.t("warning.title"), i18n.t("psd.no.doc"))
            return

        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning(i18n.t("warning.title"), "No layer selected")
            return

        idx = self._tree.index(sel[0])
        if idx >= len(self._layers):
            return

        name, path = self._layers[idx]
        layer = self._resolve_layer(path)

        image_path = filedialog.askopenfilename(
            title="Select image",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.tif *.tiff *.bmp"), ("All", "*.*")],
        )
        if not image_path:
            return

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
        """Resolve layer by path [1,2,3,...]"""
        obj = self._doc
        for idx in path:
            obj = obj.Layers.Item(idx)
        return obj

    def _find_layer_by_name(self, target_name: str):
        """Find first layer by name"""
        target_lower = target_name.lower()
        for name, path in self._layers:
            if name.lower() == target_lower:
                return (name, path)
        return None

    def _find_photo_layer(self):
        """Auto-detect photo layer"""
        # Priority 1: SO by name
        for name, path in self._layers:
            if name.lower() in self._PHOTO_SO_NAMES:
                layer = self._resolve_layer(path)
                if _is_smart_object(layer):
                    return (name, path)

        # Priority 2: Raster by keywords
        for name, path in self._layers:
            nl = name.lower()
            if any(kw in nl for kw in self._PHOTO_KEYWORDS):
                layer = self._resolve_layer(path)
                if not _is_smart_object(layer) and not _is_group(layer):
                    return (name, path)

        # Priority 3: Largest SO
        largest = None
        largest_area = 0
        for name, path in self._layers:
            key = json.dumps(path)
            if key in self._so_frames:
                l, t, r, b = self._so_frames[key]
                area = (r - l) * (b - t)
                if area > largest_area:
                    largest_area = area
                    largest = (name, path)
        return largest

    def auto_replace_photo(self):
        """Auto replace photo layer"""
        if not self._doc:
            messagebox.showwarning(i18n.t("warning.title"), i18n.t("psd.no.doc"))
            return

        found = self._find_photo_layer()
        if not found:
            messagebox.showinfo(i18n.t("info.title"), "Photo layer not found")
            return

        name, path = found
        self._log(f"Auto-detected photo layer: {name}", "info")

        image_path = filedialog.askopenfilename(
            title="Select photo",
            filetypes=[("Images", "*.jpg *.jpeg *.png"), ("All", "*.*")],
        )
        if not image_path:
            return

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
        """Open SO picker dialog"""
        if not self._doc or not self._psd_path:
            messagebox.showwarning(i18n.t("warning.title"), i18n.t("psd.no.doc"))
            return

        so_layers = []
        for name, path in self._layers:
            layer = self._resolve_layer(path)
            if _is_smart_object(layer):
                key = json.dumps(path)
                bounds = self._so_frames.get(key, (0, 0, 100, 100))
                so_layers.append((name, path, bounds))

        if not so_layers:
            messagebox.showinfo(i18n.t("info.title"), "No Smart Objects found")
            return

        def on_replace(name: str, path_key: list, img_path: str):
            try:
                layer = self._resolve_layer(path_key)
                mode = self._mode_var.get()
                frame_key = json.dumps(path_key)
                self._replace_smart_object(layer, img_path, mode, frame_key=frame_key, isolate=True)
                self._log(f"SO replaced: {name}", "ok")
            except Exception as e:
                messagebox.showerror(i18n.t("error.title"), str(e))
                self._log(f"SO replace failed: {e}", "error")

        SOPickerWindow(self.winfo_toplevel(), so_layers, self._psd_path, on_replace)

    def replace_all_photo_so(self):
        """Replace all photo SO layers with same image"""
        if not self._doc:
            messagebox.showwarning(i18n.t("warning.title"), i18n.t("psd.no.doc"))
            return

        image_path = filedialog.askopenfilename(
            title="Select photo for all SO",
            filetypes=[("Images", "*.jpg *.jpeg *.png"), ("All", "*.*")],
        )
        if not image_path:
            return

        matched = []
        for name, path in self._layers:
            if name.lower() in self._PHOTO_SO_NAMES:
                layer = self._resolve_layer(path)
                if _is_smart_object(layer):
                    matched.append((name, path, layer))

        if not matched:
            messagebox.showinfo(i18n.t("info.title"), "No matching photo SO found")
            return

        try:
            mode = self._mode_var.get()
            for name, path, layer in matched:
                frame_key = json.dumps(path)
                self._replace_smart_object(layer, image_path, mode, frame_key=frame_key)
                self._log(f"Replaced SO: {name}", "ok")

            messagebox.showinfo(i18n.t("info.title"), f"Replaced {len(matched)} SO layers")
        except Exception as e:
            messagebox.showerror(i18n.t("error.title"), str(e))
            self._log(f"Batch SO replace failed: {e}", "error")

    def batch_replace(self):
        """Simple batch: one image to one layer across multiple PSDs"""
        in_folder = self._in_var.get()
        out_folder = self._out_var.get()

        if not in_folder or not out_folder:
            messagebox.showwarning(i18n.t("warning.title"), "Set input/output folders")
            return

        in_dir = Path(in_folder)
        out_dir = Path(out_folder)
        if not in_dir.exists():
            messagebox.showerror(i18n.t("error.title"), f"Input folder not found: {in_dir}")
            return

        out_dir.mkdir(parents=True, exist_ok=True)

        images = list(in_dir.glob("*.jpg")) + list(in_dir.glob("*.png"))
        if not images:
            messagebox.showinfo(i18n.t("info.title"), "No images found in input folder")
            return

        if not self._psd_path:
            messagebox.showwarning(i18n.t("warning.title"), "Open template PSD first")
            return

        template_path = str(self._psd_path)
        found = self._find_photo_layer()
        if not found:
            messagebox.showinfo(i18n.t("info.title"), "Photo layer not found in template")
            return

        layer_name, layer_path = found
        self._log(f"Batch target layer: {layer_name}", "info")

        mode = self._mode_var.get()
        success = 0

        for img_path in images:
            stem = img_path.stem
            try:
                # Reopen template
                if success > 0:
                    try:
                        self._doc.Close(2)
                    except:
                        pass
                    self._doc = self._ps.open(template_path)
                    self.scan_layers()

                layer = self._resolve_layer(layer_path)
                frame_key = json.dumps(layer_path)
                self._replace_layer_content(layer, str(img_path), mode, frame_key=frame_key)

                out_path = out_dir / f"{stem}.psd"
                self._doc.SaveAs(str(out_path))
                self._log(f"Saved: {out_path.name}", "ok")
                success += 1

            except Exception as e:
                self._log(f"Batch failed for {stem}: {e}", "error")

        messagebox.showinfo(i18n.t("info.title"), f"Batch done: {success}/{len(images)} saved to {out_dir}")

    def batch_csv_replace(self):
        """Advanced batch: CSV mapping (output_name, layer1, layer2, ...)"""
        csv_path = filedialog.askopenfilename(
            title="Select CSV mapping",
            filetypes=[("CSV", "*.csv"), ("All", "*.*")],
        )
        if not csv_path:
            return

        out_folder = self._out_var.get()
        if not out_folder:
            messagebox.showwarning(i18n.t("warning.title"), "Set output folder")
            return

        out_dir = Path(out_folder)
        out_dir.mkdir(parents=True, exist_ok=True)

        # Parse CSV
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows_raw = list(reader)
        except Exception as e:
            messagebox.showerror(i18n.t("error.title"), f"CSV read failed: {e}")
            return

        if not rows_raw:
            messagebox.showinfo(i18n.t("info.title"), "CSV is empty")
            return

        # Expected format: output_name, <layer_columns>
        # Each cell in layer column = path to image file
        layer_columns = [c for c in rows_raw[0].keys() if c != "output_name"]
        if not layer_columns:
            messagebox.showerror(i18n.t("error.title"), "CSV must have layer columns")
            return

        rows = []
        for r in rows_raw:
            out_name = r.get("output_name", "").strip()
            if not out_name:
                continue
            photos = {}
            for col in layer_columns:
                val = r.get(col, "").strip()
                if val:
                    photos[col] = Path(val)
            if photos:
                rows.append({"output_name": out_name, "photos": photos})

        if not rows:
            messagebox.showinfo(i18n.t("info.title"), "No valid rows in CSV")
            return

        if not self._psd_path:
            messagebox.showwarning(i18n.t("warning.title"), "Open template PSD first")
            return

        self._log(f"CSV batch: {len(rows)} variant(s), {len(layer_columns)} layer(s)", "info")

        template_path = str(self._psd_path)
        success = 0

        for idx, row in enumerate(rows, start=1):
            out_name = row["output_name"]
            photos: dict[str, Path] = row["photos"]

            try:
                # Reopen template
                if idx > 1:
                    try:
                        self._doc.Close(2)
                    except:
                        pass
                    self._doc = self._ps.open(template_path)
                    self.scan_layers()

                for layer_name, photo_path in photos.items():
                    found = self._find_layer_by_name(layer_name)
                    if not found:
                        self._log(f"[{out_name}] layer '{layer_name}' not found - skip", "warn")
                        continue

                    _n, path = found
                    layer = self._resolve_layer(path)

                    self._replace_layer_content(
                        layer, str(photo_path), self._mode_var.get(),
                        frame_key=json.dumps(path),
                    )
                    self._log(f"[{out_name}] '{layer_name}' ← {photo_path.name}", "ok")

                target = out_dir / f"{out_name}.psd"
                self._doc.SaveAs(str(target))
                self._log(f"Saved: {target.name}", "ok")
                success += 1

            except Exception as exc:
                self._log(f"[{out_name}] FAILED: {exc}", "error")

        self._log(f"CSV batch complete: {success}/{len(rows)} PSD saved to {out_dir}", "ok")
        messagebox.showinfo(
            i18n.t("info.title"),
            f"Done: {success}/{len(rows)} PSD saved to:\n{out_dir}",
        )

    def _retranslate(self) -> None:
        pairs = [
            (self._btn_open, "psd.open"),
            (self._btn_scan, "psd.scan"),
            (self._btn_unlck, "psd.unlock"),
            (self._btn_repl, "psd.replace"),
            (self._btn_batch, "psd.batch"),
            (self._btn_in, "common.browse"),
            (self._btn_out, "common.browse"),
            (self._rb_fit, "psd.mode.fit"),
            (self._rb_fill, "psd.mode.fill"),
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


# Alias для импорта
PsdToolsFrameCTk = PsdToolsFrame
