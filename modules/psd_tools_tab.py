from __future__ import annotations


import json
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Optional


from core.config import config
from core.i18n import i18n


# ===== Импорт модуля умной подмены =====
from modules.image_replace import resize_with_mode
try:
    from PIL import Image
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

    def __init__(self, master: tk.Misc, log: LogFn) -> None:
        super().__init__(master, padding=(12, 8))
        self._log = log
        self._ps: Optional[PhotoshopBridge] = None
        self._doc = None
        self._psd_path: Optional[Path] = None
        self._layers_index: list[tuple[str, list]] = []
        self._so_frames: dict[str, tuple] = {}

        self._mode_var = tk.StringVar(value=config.get("psd_mode", "fill"))
        self._no_upscale_var = tk.BooleanVar(value=bool(config.get("psd_no_upscale", False)))
        self._clip_bounds_var = tk.BooleanVar(value=bool(config.get("psd_clip_to_bounds", True)))
        self._inherit_meta_var = tk.BooleanVar(value=bool(config.get("psd_inherit_metadata", True)))

        self._in_var = tk.StringVar(value=config.get("psd_in_dir"))
        self._out_var = tk.StringVar(value=config.get("psd_out_dir"))

        self._mode_var.trace_add("write",
                                 lambda *_: config.set("psd_mode", self._mode_var.get()))
        self._no_upscale_var.trace_add("write",
                                       lambda *_: config.set("psd_no_upscale", bool(self._no_upscale_var.get())))
        self._clip_bounds_var.trace_add("write",
                                        lambda *_: config.set("psd_clip_to_bounds", bool(self._clip_bounds_var.get())))
        self._inherit_meta_var.trace_add("write",
                                         lambda *_: config.set("psd_inherit_metadata", bool(self._inherit_meta_var.get())))
        self._in_var.trace_add("write",
                               lambda *_: config.set("psd_in_dir", self._in_var.get()))
        self._out_var.trace_add("write",
                                lambda *_: config.set("psd_out_dir", self._out_var.get()))

        self._build()
        i18n.subscribe(self._retranslate)

    def _build(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        self._btn_open = ttk.Button(toolbar, text=i18n.t("psd.open"), command=self.open_psd)
        self._btn_scan = ttk.Button(toolbar, text=i18n.t("psd.scan"), command=self.scan_layers)
        self._btn_unlck = ttk.Button(toolbar, text=i18n.t("psd.unlock"), command=self.unlock_all)
        self._btn_repl = ttk.Button(toolbar, text=i18n.t("psd.replace"), command=self.replace_in_selected)
        self._btn_auto = ttk.Button(toolbar, text="Авто фото", command=self.auto_replace_photo)
        for i, b in enumerate((self._btn_open, self._btn_scan, self._btn_unlck,
                                self._btn_repl, self._btn_auto)):
            b.grid(row=0, column=i, padx=(0, 6))

        left = ttk.Frame(self)
        left.grid(row=1, column=0, sticky="ns", padx=(0, 12))

        self._lbl_layers = ttk.Label(left, text=i18n.t("psd.section.layers"),
                                     font=("Segoe UI", 10, "bold"))
        self._lbl_layers.pack(anchor="w", pady=(0, 6))

        self._listbox = tk.Listbox(left, width=42, height=22, activestyle="dotbox")
        self._listbox.pack(fill="y", expand=False)

        sb = ttk.Scrollbar(left, orient="vertical", command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=sb.set)

        right = ttk.Frame(self)
        right.grid(row=1, column=1, sticky="nsew")
        right.columnconfigure(1, weight=1)

        self._lbl_actions = ttk.Label(right, text=i18n.t("psd.section.actions"),
                                     font=("Segoe UI", 10, "bold"))
        self._lbl_actions.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

        self._lbl_mode = ttk.Label(right, text=i18n.t("psd.mode"))
        self._lbl_mode.grid(row=1, column=0, sticky="w", pady=4)
        self._rb_fit = ttk.Radiobutton(right, text=i18n.t("psd.mode.fit"),
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

        self._cb_inherit_meta = ttk.Checkbutton(
            right, text=i18n.t("psd.inherit.metadata"),
            variable=self._inherit_meta_var,
        )
        self._cb_inherit_meta.grid(row=5, column=0, columnspan=4, sticky="w", pady=(2, 0))

        ttk.Separator(right, orient="horizontal").grid(
            row=6, column=0, columnspan=4, sticky="ew", pady=12,
        )

        self._lbl_batch = ttk.Label(right, text=i18n.t("psd.section.batch"),
                                    font=("Segoe UI", 10, "bold"))
        self._lbl_batch.grid(row=7, column=0, columnspan=4, sticky="w", pady=(0, 8))

        self._lbl_in = ttk.Label(right, text=i18n.t("psd.in.folder"))
        self._lbl_in.grid(row=8, column=0, sticky="w")
        ttk.Entry(right, textvariable=self._in_var).grid(row=8, column=1, columnspan=2, sticky="ew", padx=6)
        self._btn_in = ttk.Button(right, text=i18n.t("common.browse"),
                                  command=lambda: self._pick(self._in_var, "psd_in_dir"))
        self._btn_in.grid(row=8, column=3, sticky="w")

        self._lbl_out = ttk.Label(right, text=i18n.t("psd.out.folder"))
        self._lbl_out.grid(row=9, column=0, sticky="w", pady=4)
        ttk.Entry(right, textvariable=self._out_var).grid(row=9, column=1, columnspan=2, sticky="ew", padx=6, pady=4)
        self._btn_out = ttk.Button(right, text=i18n.t("common.browse"),
                                   command=lambda: self._pick(self._out_var, "psd_out_dir"))
        self._btn_out.grid(row=9, column=3, sticky="w", pady=4)

        self._btn_batch = ttk.Button(right, text=i18n.t("psd.batch"),
                                     command=self.batch_replace)
        self._btn_batch.grid(row=10, column=0, columnspan=4, sticky="ew", pady=(12, 0))

        self._warn = ttk.Label(self, text="", foreground="#c05555")
        self._warn.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))

    def _pick(self, var: tk.StringVar, cfg_key: str) -> None:
        chosen = filedialog.askdirectory(initialdir=var.get() or str(Path.home()))
        if chosen:
            var.set(chosen)
            config.set(cfg_key, chosen)

    def _ensure_ps(self) -> bool:
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
            self._warn.configure(text=f"{i18n.t('psd.no.photoshop')} ({err})")
            self._log(i18n.t("psd.no.photoshop"), "error")
            return False

        self._warn.configure(text="")
        try:
            self._ps.app.BringToFront()
        except Exception:
            pass
        return True

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
                    self._log(f"RPC error on attempt {attempt + 1}/3 – reconnecting…", "warn")
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
            " • Photoshop закрыт или ещё не готов\n"
            " • Открыт модальный диалог (Missing Fonts, Camera Raw)\n"
            " • Файл заблокирован (OneDrive/Dropbox sync)\n"
            " • Путь с не-ASCII символами"
        )
        messagebox.showerror(i18n.t("error.title"), f"{msg}{hint}")
        self._log(msg, "error")

    def scan_layers(self) -> None:
        if not self._ensure_ps() or self._doc is None:
            self._log(i18n.t("psd.no.file"), "warn")
            return
        self._layers_index.clear()
        self._listbox.delete(0, "end")
        self._so_frames.clear()
        max_depth = int(config.get("smart_object_depth", 3))
        self._walk(self._doc, path=[], depth=0, max_depth=max_depth)
        self._log(f"Layers scanned: {len(self._layers_index)}", "info")

    def _enumerate_children(self, container) -> list:
        out: list = []
        try:
            n = int(container.Layers.Count)
        except Exception:
            n = 0
        if n > 0:
            for i in range(1, n + 1):
                try:
                    out.append((container.Layers.Item(i), ("L", i)))
                except Exception:
                    continue
            return out
        try:
            for i in range(1, int(container.ArtLayers.Count) + 1):
                try:
                    out.append((container.ArtLayers.Item(i), ("A", i)))
                except Exception:
                    continue
        except Exception:
            pass
        try:
            for i in range(1, int(container.LayerSets.Count) + 1):
                try:
                    out.append((container.LayerSets.Item(i), ("S", i)))
                except Exception:
                    continue
        except Exception:
            pass
        return out

    def _walk(self, container, path: list, depth: int, max_depth: int) -> None:
        for layer, key in self._enumerate_children(container):
            name = getattr(layer, "Name", f"Layer {key[1]}")
            indent = "  " * depth

            is_group = _is_group(layer)
            is_so = (not is_group) and _is_smart_object(layer)

            marker = ""
            if is_group:
                marker = " [G]"
            elif is_so:
                marker = " [SO]"
            else:
                try:
                    b = layer.Bounds
                    w = float(b[2]) - float(b[0])
                    h = float(b[3]) - float(b[1])
                    if w <= 0 or h <= 0:
                        marker = " [empty]"
                except Exception:
                    pass

            self._listbox.insert("end", f"{indent}{name}{marker}")
            self._layers_index.append((name, path + [key]))

            if is_group and depth < max_depth:
                self._walk(layer, path + [key], depth + 1, max_depth)

    def unlock_all(self) -> None:
        if not self._ensure_ps() or self._doc is None:
            self._log(i18n.t("psd.no.file"), "warn")
            return
        count = self._unlock_recursive(self._doc)
        self._log(f"Unlocked {count} layers", "ok")

    def _unlock_recursive(self, container) -> int:
        unlocked = 0
        try:
            layer_count = container.Layers.Count
        except Exception:
            return 0
        for i in range(1, layer_count + 1):
            try:
                layer = container.Layers.Item(i)
            except Exception:
                continue
            for prop in ("AllLocked", "PixelsLocked", "PositionLocked", "TransparentPixelsLocked"):
                try:
                    setattr(layer, prop, False)
                except Exception:
                    pass
            unlocked += 1
            if _is_group(layer):
                unlocked += self._unlock_recursive(layer)
        return unlocked

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
            self._replace_layer_content(layer, image_path, self._mode_var.get(),
                                       frame_key=json.dumps(path))
            self._log(f"Replaced photo in '{name}'", "ok")
        except Exception as exc:
            messagebox.showerror(i18n.t("error.title"), str(exc))
            self._log(str(exc), "error")

    def _resolve_layer(self, path: list):
        node = self._doc
        for step in path:
            if isinstance(step, tuple):
                kind, idx = step
                if kind == "A":
                    node = node.ArtLayers.Item(idx)
                elif kind == "S":
                    node = node.LayerSets.Item(idx)
                else:
                    node = node.Layers.Item(idx)
            else:
                node = node.Layers.Item(step)
        return node

    # ============================================================
    # УМНАЯ ПОДГОТОВКА ИЗОБРАЖЕНИЯ
    # ============================================================

    def _prepare_image_for_psd(
        self,
        new_image_path: str,
        target_width: int,
        target_height: int,
        mode: str = "fill",
    ) -> str:
        """
        Приводит новое изображение ТОЧНО к размеру слоя (fill+upscale по умолчанию).
        Как фото на документы: без белых полей, обрезка лишнего по бокам.
        """
        if not PIL_AVAILABLE:
            self._log("Pillow недоступен, пропускаем подготовку", "warn")
            return new_image_path

        if target_width <= 0 or target_height <= 0:
            self._log(f"Target bounds invalid ({target_width}x{target_height})", "warn")
            return new_image_path

        try:
            with Image.open(new_image_path) as new_img:
                new_img.load()
                result_img = resize_with_mode(
                    new_img,
                    (target_width, target_height),
                    mode="fill",
                    no_upscale=False,
                )
                if result_img.mode not in ("RGB", "RGBA"):
                    result_img = result_img.convert("RGB")
                self._log(
                    f"Prepare: {new_img.size[0]}x{new_img.size[1]} → "
                    f"{target_width}x{target_height} (fill, upscale)",
                    "info",
                )
                return self._save_temp(result_img, new_image_path)
        except Exception as e:
            self._log(f"Prepare failed: {e}", "warn")
            return new_image_path

    def _save_temp(self, img, original_path: str) -> str:
        temp_dir = Path(original_path).parent / ".prizma_temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_file = temp_dir / f"prepared_{Path(original_path).stem}.png"
        img.save(temp_file, format="PNG", optimize=False)
        return str(temp_file)

    # ============================================================
    # SMART OBJECT REPLACE (ЖЁСТКО fill в размер рамки)
    # ============================================================

    def _replace_smart_object(self, so_layer, image_path: str, mode: str,
                              frame_key: Optional[str] = None) -> None:
        """
        Всегда fill в точный размер рамки SO. Как фото на документы.
        """
        self._doc.ActiveLayer = so_layer

        # 1) Целевая рамка SO
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
        except Exception as e:
            self._log(f"SO bounds read failed: {e}", "warn")
            fw = fh = 0

        # 2) Готовим картинку точно в размер рамки
        prepared_path = image_path
        if PIL_AVAILABLE and fw > 0 and fh > 0:
            prepared_path = self._prepare_image_for_psd(image_path, fw, fh)

        # 3) Вызов JSX
        stored = self._so_frames.get(frame_key) if frame_key else None
        frame_literal = ",".join(f"{v:.3f}" for v in stored) if stored else "AUTO"

        returned = self._run_so_replace_contents_jsx(prepared_path, "exact", frame_literal)
        if frame_key and returned:
            self._so_frames[frame_key] = returned

    def _run_so_replace_contents_jsx(self, image_path: str, mode: str,
                                     frame_literal: str):
        path_literal = json.dumps(str(Path(image_path)))

        jsx = r"""
(function () {
    var NEW_PATH = __PATH__;
    var FRAME = "__FRAME__";

    var doc = app.activeDocument;
    var so = doc.activeLayer;

    var savedRulerUnits = app.preferences.rulerUnits;
    var savedTypeUnits = app.preferences.typeUnits;
    app.preferences.rulerUnits = Units.PIXELS;
    app.preferences.typeUnits = TypeUnits.PIXELS;

    function asPx(v){ try { return v.as('px'); } catch(e){ return Number(v); } }

    var FL, FT, FR, FB;
    if (FRAME === "AUTO") {
        var ob = so.bounds;
        FL = asPx(ob[0]); FT = asPx(ob[1]);
        FR = asPx(ob[2]); FB = asPx(ob[3]);
    } else {
        var parts = FRAME.split(",");
        FL = parseFloat(parts[0]); FT = parseFloat(parts[1]);
        FR = parseFloat(parts[2]); FB = parseFloat(parts[3]);
    }
    var FW = FR - FL, FH = FB - FT;

    // Замена содержимого SO
    var d = new ActionDescriptor();
    d.putPath(charIDToTypeID('null'), new File(NEW_PATH));
    try { d.putInteger(charIDToTypeID('PgNm'), 1); } catch(e) {}
    executeAction(stringIDToTypeID('placedLayerReplaceContents'),
                  d, DialogModes.NO);

    so = doc.activeLayer;

    // Жёсткий подгон SO в размер FW×FH (aspect уже правильный из Python).
    if (FW > 0 && FH > 0) {
        var b = so.bounds;
        var w = asPx(b[2]) - asPx(b[0]);
        var h = asPx(b[3]) - asPx(b[1]);
        if (w > 0 && h > 0) {
            var sx = FW / w;
            var sy = FH / h;
            so.resize(sx * 100.0, sy * 100.0, AnchorPosition.MIDDLECENTER);
        }
    }

    // Центрируем по рамке
    var nb = so.bounds;
    var cx = (asPx(nb[0]) + asPx(nb[2])) / 2;
    var cy = (asPx(nb[1]) + asPx(nb[3])) / 2;
    so.translate((FL + FR) / 2 - cx, (FT + FB) / 2 - cy);

    app.preferences.rulerUnits = savedRulerUnits;
    app.preferences.typeUnits = savedTypeUnits;

    return FL + "|" + FT + "|" + FR + "|" + FB;
})();
"""
        jsx = jsx.replace("__PATH__", path_literal).replace("__FRAME__", frame_literal)
        result = self._ps.app.DoJavaScript(jsx)
        raw = str(result).strip() if result is not None else ""
        parts = raw.split("|")
        if len(parts) == 4:
            try:
                frame = tuple(float(p) for p in parts)
                self._log(
                    f"SO replace: frame {frame[2]-frame[0]:.0f}x{frame[3]-frame[1]:.0f}px, mode=exact-fill",
                    "info",
                )
                return frame
            except ValueError:
                pass
        return None

    # ============================================================
    # RASTER REPLACE (merge down)
    # ============================================================

    def _replace_layer_content(self, layer, image_path: str, mode: str,
                               frame_key: Optional[str] = None) -> None:
        if _is_group(layer):
            raise RuntimeError("Selected item is a group (LayerSet), not a photo layer.")

        if _is_smart_object(layer):
            self._replace_smart_object(layer, image_path, mode, frame_key)
        else:
            self._replace_raster_merge_down(layer, image_path, mode)

    def _replace_raster_merge_down(self, layer, image_path: str, mode: str) -> None:
        prepared_path = image_path
        try:
            bounds = layer.Bounds
            target_width = int(float(bounds[2]) - float(bounds[0]))
            target_height = int(float(bounds[3]) - float(bounds[1]))

            if target_width > 0 and target_height > 0:
                prepared_path = self._prepare_image_for_psd(
                    image_path, target_width, target_height
                )
        except Exception as e:
            self._log(f"Prep raster failed: {e}", "warn")

        self._doc.ActiveLayer = layer
        self._run_merge_down_jsx(prepared_path, "exact")

    def _run_merge_down_jsx(self, image_path: str, mode: str) -> None:
        path_literal = json.dumps(str(Path(image_path)))
        clip_literal = "true" if bool(config.get("psd_clip_to_bounds", True)) else "false"

        jsx = r"""
(function () {
    var NEW_PATH = __PATH__;
    var CLIP = __CLIP__;

    var doc = app.activeDocument;
    var target = doc.activeLayer;
    var targetName = target.name;

    var savedRulerUnits = app.preferences.rulerUnits;
    var savedTypeUnits = app.preferences.typeUnits;
    app.preferences.rulerUnits = Units.PIXELS;
    app.preferences.typeUnits = TypeUnits.PIXELS;

    function asPx(v){ try { return v.as('px'); } catch(e){ return Number(v); } }

    var b = target.bounds;
    var L = asPx(b[0]), T = asPx(b[1]), R = asPx(b[2]), Bt = asPx(b[3]);
    var W = R - L, H = Bt - T;
    var usedCanvas = false;
    var diagW = W, diagH = H;

    if (W <= 0 || H <= 0) {
        L = 0; T = 0;
        R = asPx(doc.width); Bt = asPx(doc.height);
        W = R - L; H = Bt - T;
        usedCanvas = true;
    }
    if (W <= 0 || H <= 0) {
        app.preferences.rulerUnits = savedRulerUnits;
        app.preferences.typeUnits = savedTypeUnits;
        throw new Error("Empty bounds and canvas.");
    }

    try { target.allLocked = false; } catch(e) {}
    try { target.pixelsLocked = false; } catch(e) {}
    try { target.positionLocked = false; } catch(e) {}
    try { target.transparentPixelsLocked = false; } catch(e) {}

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

    // Жёстко подгоняем placed в размер W×H (без сохранения aspect,
    // потому что Python уже привёл картинку к правильному aspect через fill+crop)
    var pb = placed.bounds;
    var pw = asPx(pb[2]) - asPx(pb[0]);
    var ph = asPx(pb[3]) - asPx(pb[1]);
    if (pw > 0 && ph > 0) {
        var sx = W / pw;
        var sy = H / ph;
        placed.resize(sx * 100.0, sy * 100.0, AnchorPosition.MIDDLECENTER);
    }

    // Центрируем
    pb = placed.bounds;
    var cx = (asPx(pb[0]) + asPx(pb[2])) / 2;
    var cy = (asPx(pb[1]) + asPx(pb[3])) / 2;
    placed.translate((L + R) / 2 - cx, (T + Bt) / 2 - cy);

    try { placed.rasterize(RasterizeType.ENTIRELAYER); } catch(e) {}

    if (CLIP) {
        try {
            doc.selection.select([[L,T],[R,T],[R,Bt],[L,Bt]], SelectionType.REPLACE);
            doc.selection.invert();
            doc.activeLayer = placed;
            try { doc.selection.clear(); } catch(e) {}
            try { doc.selection.deselect(); } catch(e) {}
        } catch(e) {}
    }

    var mergeStatus = "MERGED";
    try {
        placed.merge();
    } catch (mergeErr) {
        mergeStatus = "FALLBACK";
        try {
            doc.activeLayer = target;
            try { target.isBackgroundLayer = false; } catch(e) {}
            try { target.allLocked = false; } catch(e) {}
            target.remove();
        } catch (rmErr) {}
        try { doc.activeLayer = placed; } catch(e) {}
    }

    try { doc.activeLayer.name = targetName; } catch(e) {}

    app.preferences.rulerUnits = savedRulerUnits;
    app.preferences.typeUnits = savedTypeUnits;

    return mergeStatus + "|" + diagW + "|" + diagH + "|" + (usedCanvas ? "1" : "0");
})();
"""
        jsx = jsx.replace("__PATH__", path_literal).replace("__CLIP__", clip_literal)
        result = self._ps.app.DoJavaScript(jsx)
        status_raw = str(result).strip() if result is not None else ""
        parts = status_raw.split("|")
        status = parts[0] if parts else ""
        diag_w = parts[1] if len(parts) > 1 else "?"
        diag_h = parts[2] if len(parts) > 2 else "?"
        used_canvas = parts[3] == "1" if len(parts) > 3 else False
        self._log(
            f"Raster bounds: {diag_w}x{diag_h}px"
            + (" (fallback → canvas)" if used_canvas else ""),
            "info",
        )
        if status == "FALLBACK":
            self._log("merge_down недоступен: placed оставлен вместо target", "warn")

    # ============================================================
    # АВТОПОИСК СЛОЯ ДЛЯ ФОТО
    # ============================================================

    def _find_photo_layer(self) -> Optional[tuple[str, list]]:
        """
        Автопоиск слоя-плейсхолдера. Приоритеты:
        1. SO с ключевым словом в имени (самый большой)
        2. Растровый слой с ключевым словом
        3. Самый большой SO
        """
        if not self._layers_index:
            return None

        so_by_name: list = []
        raster_by_name: list = []
        all_so: list = []

        for (name, path) in self._layers_index:
            try:
                layer = self._resolve_layer(path)
            except Exception:
                continue
            if _is_group(layer):
                continue

            area = 0.0
            try:
                b = layer.Bounds
                w = float(b[2]) - float(b[0])
                h = float(b[3]) - float(b[1])
                area = max(0.0, w * h)
            except Exception:
                pass

            is_so = _is_smart_object(layer)
            name_low = name.lower().strip()
            keyword_hit = any(kw in name_low for kw in self._PHOTO_KEYWORDS)

            if is_so:
                all_so.append((area, name, path))
                if keyword_hit:
                    so_by_name.append((area, name, path))
            else:
                if keyword_hit and area > 0:
                    raster_by_name.append((area, name, path))

        if so_by_name:
            so_by_name.sort(key=lambda t: -t[0])
            _, name, path = so_by_name[0]
            self._log(f"Auto: SO по имени → '{name}'", "info")
            return (name, path)

        if raster_by_name:
            raster_by_name.sort(key=lambda t: -t[0])
            _, name, path = raster_by_name[0]
            self._log(f"Auto: растр по имени → '{name}'", "info")
            return (name, path)

        if all_so:
            all_so.sort(key=lambda t: -t[0])
            _, name, path = all_so[0]
            self._log(f"Auto: самый большой SO → '{name}'", "info")
            return (name, path)

        return None

    def auto_replace_photo(self) -> None:
        """Один клик: найти слой + подставить фото."""
        if not self._ensure_ps() or self._doc is None:
            self._log(i18n.t("psd.no.file"), "warn")
            return

        if not self._layers_index:
            self.scan_layers()

        found = self._find_photo_layer()
        if not found:
            messagebox.showwarning(
                i18n.t("info.title"),
                "Не удалось автоматически найти слой для фото.\n\n"
                "Возможные причины:\n"
                " • В PSD нет Smart Object слоёв\n"
                " • Слои названы нестандартно\n\n"
                "Выбери слой вручную из списка слева.",
            )
            return

        name, path = found

        # Подсветим слой
        try:
            for idx, (nm, pt) in enumerate(self._layers_index):
                if nm == name and pt == path:
                    self._listbox.selection_clear(0, "end")
                    self._listbox.selection_set(idx)
                    self._listbox.activate(idx)
                    self._listbox.see(idx)
                    break
        except Exception:
            pass

        image_path = filedialog.askopenfilename(
            title=f"Фото для '{name}'",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.tif *.tiff *.bmp"), ("All", "*.*")],
        )
        if not image_path:
            return

        try:
            layer = self._resolve_layer(path)
            self._replace_layer_content(layer, image_path, self._mode_var.get(),
                                        frame_key=json.dumps(path))
            self._log(f"Auto: фото подставлено в '{name}'", "ok")
        except Exception as exc:
            messagebox.showerror(i18n.t("error.title"), str(exc))
            self._log(str(exc), "error")

    # ============================================================
    # BATCH
    # ============================================================

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
        frame_key = json.dumps(path)
        for img in images:
            try:
                layer = self._resolve_layer(path)
                self._replace_layer_content(layer, str(img), self._mode_var.get(),
                                           frame_key=frame_key)
                target = out_dir / f"{self._psd_path.stem}__{img.stem}.psd"
                self._doc.SaveAs(str(target))
                self._log(f"Saved: {target.name}", "ok")
            except Exception as exc:
                self._log(f"{img.name}: {exc}", "error")
        self._log(i18n.t("psd.done"), "ok")

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
        # "Авто фото" — без i18n, просто русский текст
        self._btn_auto.configure(text="Авто фото")
        self._lbl_layers.configure(text=i18n.t("psd.section.layers"))
        self._lbl_actions.configure(text=i18n.t("psd.section.actions"))
        self._lbl_batch.configure(text=i18n.t("psd.section.batch"))
        self._lbl_mode.configure(text=i18n.t("psd.mode"))
        self._lbl_mode_hint.configure(text=i18n.t("psd.mode.hint"))
        self._lbl_in.configure(text=i18n.t("psd.in.folder"))
        self._lbl_out.configure(text=i18n.t("psd.out.folder"))
        if self._ps and not self._ps.available:
            self._warn.configure(text=f"{i18n.t('psd.no.photoshop')} ({self._ps.error()})")
