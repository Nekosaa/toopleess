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

    # Порог: если min(sw, sh) < этого значения — спросить у юзера подтверждение
    _MIN_SOURCE_SIDE = 400

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

        # Флаг «пользователь уже подтвердил мелкий исходник в этой сессии» —
        # чтобы не спрашивать 20 раз при batch.
        self._small_source_ack = False

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
        self._btn_picker = ttk.Button(toolbar, text="Выбор SO", command=self.open_so_picker)
        for i, b in enumerate((self._btn_open, self._btn_scan, self._btn_unlck,
                               self._btn_repl, self._btn_auto, self._btn_picker)):
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

        # Каждый новый PSD — сбрасываем ACK на мелкий исходник
        self._small_source_ack = False

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
    # УМНАЯ ПОДГОТОВКА ИЗОБРАЖЕНИЯ (ИСПРАВЛЕНО)
    # ============================================================

    def _prepare_image_for_psd(
        self,
        new_image_path: str,
        target_width: int,
        target_height: int,
        mode: str = "fill",
        force_mode: Optional[str] = None,
        use_padding: bool = False,
    ) -> str:
        """
        ИСПРАВЛЕНО: добавлен use_padding для Smart Objects.
        
        Готовит картинку под слот.
        force_mode: если задан ("fill"/"fit"/...), игнорирует режим из UI.
        use_padding: если True, использует prepare_for_smart_object (ФИКС 2).
        """
        if not PIL_AVAILABLE:
            self._log("Pillow недоступен, пропускаем подготовку", "warn")
            return new_image_path
        if target_width <= 0 or target_height <= 0:
            self._log(f"Target bounds invalid ({target_width}x{target_height})", "warn")
            return new_image_path

        try:
            no_upscale = bool(self._no_upscale_var.get())
        except Exception:
            no_upscale = False

        if force_mode:
            effective_mode = force_mode
        else:
            try:
                ui_mode = self._mode_var.get() or mode
            except Exception:
                ui_mode = mode
            effective_mode = ui_mode or "fill"

        try:
            with Image.open(new_image_path) as new_img:
                new_img.load()
                sw, sh = new_img.size
                scale = max(target_width / max(sw, 1), target_height / max(sh, 1))

                # Проверка на мелкий исходник
                if (min(sw, sh) < self._MIN_SOURCE_SIDE
                    and not no_upscale
                    and not self._small_source_ack):
                    proceed = messagebox.askyesno(
                        "Мелкое фото",
                        f"Исходник {sw}×{sh}, слот {target_width}×{target_height}"
                        f" (upscale x{scale:.1f}).\n\n"
                        f"Результат будет мыльный.\n\n"
                        f"Продолжить?",
                    )
                    if not proceed:
                        self._log("Замена отменена пользователем (мелкий исходник)", "warn")
                        return new_image_path
                    self._small_source_ack = True

                if scale > 2.0 and not no_upscale:
                    self._log(
                        f"⚠ Upscale x{scale:.1f}: применяю LANCZOS + sharpen.",
                        "warn",
                    )

                # ФИКС 2: для SO используем prepare_for_smart_object
                if use_padding:
                    result_img = prepare_for_smart_object(new_img, target_width, target_height)
                else:
                    result_img = resize_with_mode(
                        new_img,
                        target_width,
                        target_height,
                        mode=effective_mode,
                        no_upscale=no_upscale,
                    )

                # Sharpen при апскейле
                if scale > 1.5 and not no_upscale:
                    try:
                        result_img = result_img.filter(
                            ImageFilter.UnsharpMask(radius=1.5, percent=110, threshold=3)
                        )
                    except Exception as e:
                        self._log(f"Unsharp failed (skip): {e}", "warn")

                if result_img.mode not in ("RGB", "RGBA"):
                    result_img = result_img.convert("RGB")

                self._log(
                    f"Prepare: {sw}×{sh} → {result_img.size[0]}×{result_img.size[1]} "
                    f"({effective_mode}, "
                    f"{'padding' if use_padding else ('no-upscale' if no_upscale else f'upscale x{scale:.1f}')})",
                    "info",
                )
                return self._save_temp(result_img, new_image_path)
        except Exception as e:
            self._log(f"Prepare failed: {e}, using original", "warn")
            return new_image_path

    def _save_temp(self, img, original_path: str) -> str:
        """ИСПРАВЛЕНО: обработка ошибок при сохранении"""
        try:
            temp_dir = Path(original_path).parent / ".prizma_temp"
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_file = temp_dir / f"prepared_{Path(original_path).stem}.png"
            img.save(temp_file, format="PNG", optimize=False)
            return str(temp_file)
        except Exception as e:
            self._log(f"Temp save failed: {e}, using original", "warn")
            return original_path

    # ============================================================
    # SMART OBJECT REPLACE (ИСПРАВЛЕНО)
    # ============================================================

    def _read_so_true_size(self, so_layer=None) -> Optional[tuple[float, float]]:
        """
        ФИКС 1: Улучшенное чтение нативного размера SO.
        
        Читает НАТИВНЫЙ размер вложенного контента SO (ключ "size").
        Fallback 1: transform/nonAffine (размер на холсте)
        Fallback 2: editContents (УЛУЧШЕНИЕ 5)
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
        
        // ФИКС 1: проверка через link (embedded/linked content)
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
        
        // 2) fallback: размер на холсте (может дать неверный масштаб при перспективе)
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
            if not raw or raw.startswith("ERR"):
                self._log(f"SO true-size: {raw or 'no result'}, trying editContents fallback", "warn")
                # УЛУЧШЕНИЕ 5: fallback через editContents
                return self._read_so_size_via_edit_contents(so_layer)
            parts = raw.split("|")
            if len(parts) < 2:
                return None
            w = float(parts[0]); h = float(parts[1])
            src = parts[2] if len(parts) > 2 else "?"
            if w > 0 and h > 0:
                self._log(f"SO content size source: {src} ({w:.0f}x{h:.0f}px)", "info")
                return (w, h)
        except Exception as e:
            self._log(f"SO true-size read failed: {e}", "warn")
        return None

    def _read_so_size_via_edit_contents(self, so_layer) -> Optional[tuple[float, float]]:
        """
        УЛУЧШЕНИЕ 5: Fallback для edge cases.
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
            if not result.startswith("ERR"):
                parts = result.split("|")
                w = float(parts[0])
                h = float(parts[1])
                self._log(f"SO size via editContents: {w:.0f}x{h:.0f}px", "info")
                return (w, h)
        except Exception as e:
            self._log(f"Edit contents fallback failed: {e}", "error")
        return None

    def _replace_smart_object(self, so_layer, image_path: str, mode: str,
                             frame_key: Optional[str] = None,
                             isolate: bool = False) -> None:
        self._doc.ActiveLayer = so_layer

        fw = fh = 0
        true_size = self._read_so_true_size(so_layer)
        if true_size:
            fw = int(round(true_size[0]))
            fh = int(round(true_size[1]))
            self._log(f"SO content frame: {fw}x{fh}px", "info")
        else:
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
                self._log(f"SO AABB fallback: {fw}x{fh}px", "warn")
            except Exception as e:
                self._log(f"SO bounds read failed: {e}", "warn")
                fw = fh = 0

        # ФИКС 2: используем prepare_for_smart_object (padding mode)
        prepared_path = image_path
        if PIL_AVAILABLE and fw > 0 and fh > 0:
            prepared_path = self._prepare_image_for_psd(
                image_path, fw, fh, mode="fill", force_mode="fill", use_padding=True
            )

        stored = self._so_frames.get(frame_key) if frame_key else None
        frame_literal = ",".join(f"{v:.3f}" for v in stored) if stored else "AUTO"

        returned = self._run_so_replace_contents_jsx(
            prepared_path, "exact", frame_literal, isolate=isolate,
        )
        if frame_key and returned:
            self._so_frames[frame_key] = returned

    def _run_so_replace_contents_jsx(self, image_path: str, mode: str,
                                     frame_literal: str, isolate: bool = False):
        """
        ФИКС 3: Добавлена проверка correspondence после замены.
        
        Замена контента Smart Object.
        Photoshop САМ сохраняет трансформацию контейнера (перспектива/наклон/
        поворот), маску слоя и стили (fx).
        """
        path_literal = json.dumps(str(Path(image_path)))
        isolate_literal = "true" if isolate else "false"

        jsx = r"""
(function () {
    var NEW_PATH = __PATH__;
    var ISOLATE = __ISOLATE__;

    var doc = app.activeDocument;

    var savedRulerUnits = app.preferences.rulerUnits;
    var savedTypeUnits = app.preferences.typeUnits;
    app.preferences.rulerUnits = Units.PIXELS;
    app.preferences.typeUnits = TypeUnits.PIXELS;

    function dist(x1,y1,x2,y2){var dx=x2-x1,dy=y2-y1;return Math.sqrt(dx*dx+dy*dy);}

    function readSOQuad() {
        var o = { ok:false, angle:0, flipped:false, hasSkew:false,
                 tl_x:0, tl_y:0, tr_x:0, tr_y:0, br_x:0, br_y:0, bl_x:0, bl_y:0,
                 w:0, h:0 };
        try {
            var ref = new ActionReference();
            ref.putEnumerated(charIDToTypeID("Lyr "),
                            charIDToTypeID("Ordn"),
                            charIDToTypeID("Trgt"));
            var lyrDesc = executeActionGet(ref);
            var soDesc = lyrDesc.getObjectValue(stringIDToTypeID("smartObject"));
            var t = soDesc.getList(stringIDToTypeID("transform"));
            o.tl_x=t.getDouble(0); o.tl_y=t.getDouble(1);
            o.tr_x=t.getDouble(2); o.tr_y=t.getDouble(3);
            o.br_x=t.getDouble(4); o.br_y=t.getDouble(5);
            o.bl_x=t.getDouble(6); o.bl_y=t.getDouble(7);
            var dxTop=o.tr_x-o.tl_x, dyTop=o.tr_y-o.tl_y;
            var dxLeft=o.bl_x-o.tl_x, dyLeft=o.bl_y-o.tl_y;
            o.angle=Math.atan2(dyTop,dxTop)*180/Math.PI;
            o.flipped=((dxTop*dyLeft - dyTop*dxLeft) < 0);
            o.w=dist(o.tl_x,o.tl_y,o.tr_x,o.tr_y);
            o.h=dist(o.tl_x,o.tl_y,o.bl_x,o.bl_y);
            var wBottom=dist(o.bl_x,o.bl_y,o.br_x,o.br_y);
            var hRight =dist(o.tr_x,o.tr_y,o.br_x,o.br_y);
            var wDiff=Math.abs(o.w-wBottom)/Math.max(o.w,0.001);
            var hDiff=Math.abs(o.h-hRight )/Math.max(o.h,0.001);
            var dotTL=dxTop*dxLeft+dyTop*dyLeft;
            var cosA =Math.abs(dotTL/((o.w*o.h)+0.001));
            o.hasSkew=(wDiff>0.005 || hDiff>0.005 || cosA>0.01);
            o.ok=true;
        } catch(e) {}
        return o;
    }

    var before = readSOQuad();

    var isolateStatus = "skip";
    if (ISOLATE) {
        try { doc.selection.deselect(); } catch(_) {}
        try {
            executeAction(stringIDToTypeID("placedLayerNewViaCopy"),
                         undefined, DialogModes.NO);
            isolateStatus = "ok";
        } catch(e) {
            isolateStatus = "FAILED:" + ((e && e.message) ? e.message : String(e));
        }
    }

    // ЕДИНСТВЕННОЕ действие: заменить контент
    var d0 = new ActionDescriptor();
    d0.putPath(charIDToTypeID('null'), new File(NEW_PATH));
    try { d0.putInteger(charIDToTypeID('PgNm'), 1); } catch(e) {}
    executeAction(stringIDToTypeID('placedLayerReplaceContents'), d0, DialogModes.NO);

    // ФИКС 3: проверка correspondence после замены
    var after = readSOQuad();
    var finalW = 0, finalH = 0;
    try {
        var refAfter = new ActionReference();
        refAfter.putEnumerated(charIDToTypeID("Lyr "),
                              charIDToTypeID("Ordn"),
                              charIDToTypeID("Trgt"));
        var lyrDescAfter = executeActionGet(refAfter);
        var soDescAfter = lyrDescAfter.getObjectValue(stringIDToTypeID("smartObject"));
        if (soDescAfter.hasKey(stringIDToTypeID("size"))) {
            var fs = soDescAfter.getObjectValue(stringIDToTypeID("size"));
            finalW = fs.getUnitDoubleValue(stringIDToTypeID("width"));
            finalH = fs.getUnitDoubleValue(stringIDToTypeID("height"));
        }
    } catch(e) {}

    app.preferences.rulerUnits = savedRulerUnits;
    app.preferences.typeUnits = savedTypeUnits;

    var transformed = before.ok && (before.hasSkew
                                   || Math.abs(before.angle) > 1.0
                                   || before.flipped);
    return before.tl_x + "|" + before.tl_y + "|" + before.tr_x + "|" + before.tr_y
         + "|" + before.br_x + "|" + before.br_y + "|" + before.bl_x + "|" + before.bl_y
         + "|" + before.angle.toFixed(2)
         + "|" + (before.flipped ? "1" : "0")
         + "|" + (before.hasSkew ? "1" : "0")
         + "|" + (transformed ? "1" : "0")
         + "|" + before.w.toFixed(1) + "|" + before.h.toFixed(1)
         + "|pure-replace"
         + "|" + isolateStatus
         + "|finalSize:" + finalW.toFixed(0) + "x" + finalH.toFixed(0);
})();
"""
        jsx = (jsx
               .replace("__PATH__", path_literal)
               .replace("__ISOLATE__", isolate_literal))
        result = self._ps.app.DoJavaScript(jsx)
        raw = str(result).strip() if result is not None else ""
        parts = raw.split("|")

        if len(parts) >= 8:
            try:
                corners = tuple(float(p) for p in parts[:8])
                transformed = parts[11] == "1" if len(parts) > 11 else False
                method = parts[14] if len(parts) > 14 else "?"
                iso_status = parts[15] if len(parts) > 15 else "skip"
                
                # ФИКС 3: парсим finalSize
                final_size_str = "unknown"
                if len(parts) > 16 and "finalSize:" in parts[16]:
                    final_size_str = parts[16].replace("finalSize:", "")

                xs = [corners[0], corners[2], corners[4], corners[6]]
                ys = [corners[1], corners[3], corners[5], corners[7]]
                frame = (min(xs), min(ys), max(xs), max(ys))

                if iso_status.startswith("FAILED"):
                    self._log(f"SO isolate FAILED: {iso_status[7:]}", "warn")

                self._log(
                    f"SO replace: {method}, "
                    f"frame {frame[2]-frame[0]:.0f}x{frame[3]-frame[1]:.0f}px, "
                    f"{'transformed' if transformed else 'flat'}, "
                    f"content: {final_size_str}",
                    "info",
                )
                return frame
            except ValueError:
                pass
        return None

    # ============================================================
    # RASTER REPLACE
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

    var pb = placed.bounds;
    var pw = asPx(pb[2]) - asPx(pb[0]);
    var ph = asPx(pb[3]) - asPx(pb[1]);
    if (pw > 0 && ph > 0) {
        var sx = W / pw;
        var sy = H / ph;
        placed.resize(sx * 100.0, sy * 100.0, AnchorPosition.MIDDLECENTER);
    }

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
    # SO PICKER
    # ============================================================

    def open_so_picker(self) -> None:
        if not self._ensure_ps() or self._doc is None:
            self._log(i18n.t("psd.no.file"), "warn")
            return

        if not self._layers_index:
            self.scan_layers()

        so_layers: list[tuple[str, list, tuple]] = []
        for (name, path) in self._layers_index:
            try:
                layer = self._resolve_layer(path)
            except Exception:
                continue
            if _is_group(layer):
                continue
            if not _is_smart_object(layer):
                continue
            try:
                b = layer.Bounds
                bounds = (float(b[0]), float(b[1]), float(b[2]), float(b[3]))
            except Exception:
                bounds = (0.0, 0.0, 0.0, 0.0)
            so_layers.append((name, path, bounds))

        if not so_layers:
            messagebox.showinfo(
                i18n.t("info.title"),
                "В PSD не найдено ни одного Smart Object.",
            )
            return

        self._log(f"SO picker: найдено {len(so_layers)} SO-слоёв", "info")

        SOPickerWindow(
            master=self,
            so_layers=so_layers,
            psd_path=self._psd_path,
            on_replace=self._on_so_picked,
        )

    def _on_so_picked(self, name: str, path: list, image_path: str) -> None:
        """ИСПРАВЛЕНО: isolate=False по умолчанию"""
        try:
            layer = self._resolve_layer(path)
            if not _is_smart_object(layer):
                raise RuntimeError(f"Слой '{name}' не является Smart Object")

            self._replace_smart_object(
                layer, image_path,
                mode="fill",
                frame_key=json.dumps(path),
                isolate=False,
            )
            self._log(
                f"SO picker: заменено только в '{name}' (связанные копии не тронуты)",
                "ok",
            )
        except Exception as exc:
            messagebox.showerror(i18n.t("error.title"), str(exc))
            self._log(str(exc), "error")

    # ============================================================
    # АВТОПОИСК СЛОЯ ДЛЯ ФОТО
    # ============================================================

    def _find_photo_layer(self) -> Optional[tuple[str, list]]:
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
    # BATCH (ИСПРАВЛЕНО)
    # ============================================================

    def batch_replace(self) -> None:
        """ИСПРАВЛЕНО: добавлен счётчик успешных операций"""
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

        # ИСПРАВЛЕНИЕ: сбрасываем ACK перед batch
        self._small_source_ack = False

        self._log(f"Batch: {len(images)} image(s) → layer '{name}'", "info")
        frame_key = json.dumps(path)

        success_count = 0
        for img in images:
            try:
                layer = self._resolve_layer(path)
                self._replace_layer_content(layer, str(img), self._mode_var.get(),
                                           frame_key=frame_key)
                target = out_dir / f"{self._psd_path.stem}__{img.stem}.psd"
                self._doc.SaveAs(str(target))
                self._log(f"Saved: {target.name}", "ok")
                success_count += 1
            except Exception as exc:
                self._log(f"{img.name}: {exc}", "error")

        self._log(f"Batch complete: {success_count}/{len(images)} успешно", "ok")

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
        self._lbl_layers.configure(text=i18n.t("psd.section.layers"))
        self._lbl_actions.configure(text=i18n.t("psd.section.actions"))
        self._lbl_batch.configure(text=i18n.t("psd.section.batch"))
        self._lbl_mode.configure(text=i18n.t("psd.mode"))
        self._lbl_mode_hint.configure(text=i18n.t("psd.mode.hint"))
        self._lbl_in.configure(text=i18n.t("psd.in.folder"))
        self._lbl_out.configure(text=i18n.t("psd.out.folder"))
        if self._ps and not self._ps.available:
            self._warn.configure(text=f"{i18n.t('psd.no.photoshop')} ({self._ps.error()})")
