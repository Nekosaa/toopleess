"""
Prizma Studio — окно выбора Smart Object с превью.
Позволяет заменить фото только в одной копии SO, не затрагивая связанные.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Callable, Optional

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from psd_tools import PSDImage
    PSD_TOOLS_AVAILABLE = True
except ImportError:
    PSD_TOOLS_AVAILABLE = False


# Callback: (name, path_in_index, image_file_path) -> None
ReplaceCallback = Callable[[str, list, str], None]


class SOPickerWindow(tk.Toplevel):
    """
    Модальное окно со всеми SO-слоями и превью.
    Клик на «Заменить» → выбор фото → callback с флагом изолированной замены.
    """

    THUMB_SIZE = (160, 160)
    COLUMNS = 3

    def __init__(
        self,
        master: tk.Misc,
        so_layers: list[tuple[str, list, tuple]],  # (name, path, bounds)
        psd_path: Optional[Path],
        on_replace: ReplaceCallback,
    ) -> None:
        super().__init__(master)
        self.title("Выбор Smart Object для замены")
        self.geometry("720x560")
        self.configure(bg="#2b2b2b")
        self.transient(master)
        try:
            self.grab_set()
        except Exception:
            pass

        self._so_layers = so_layers
        self._psd_path = psd_path
        self._on_replace = on_replace
        self._photo_refs: dict[int, "ImageTk.PhotoImage"] = {}

        self._build_ui()
        self._load_previews()

    def _build_ui(self) -> None:
        header = ttk.Label(
            self,
            text=(
                "Найдены следующие Smart Object слои. "
                "Нажми «Заменить» под нужным — замена не затронет остальные копии."
            ),
            wraplength=680,
            justify="left",
            padding=(12, 8),
        )
        header.pack(fill="x")

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        canvas = tk.Canvas(container, bg="#2b2b2b", highlightthickness=0)
        canvas.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        sb.pack(side="right", fill="y")
        canvas.configure(yscrollcommand=sb.set)

        self._grid_frame = ttk.Frame(canvas)
        canvas_win = canvas.create_window((0, 0), window=self._grid_frame, anchor="nw")

        def _on_configure(_):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(canvas_win, width=canvas.winfo_width())

        self._grid_frame.bind("<Configure>", _on_configure)
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(canvas_win, width=e.width),
        )

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(bottom, text="Закрыть", command=self.destroy).pack(side="right")

    def _load_previews(self) -> None:
        """
        Строит сетку карточек. Превью через psd-tools:
          - не фильтруем по kind (linked/embedded SO тоже пойдут)
          - composite(force=True) → topil() → skip
          - матчинг по (имя + ближайший размер) — для дубликатов имён
        """
        # collected: [(name, width, height, PIL.Image thumbnail)]
        collected: list[tuple[str, int, int, "Image.Image"]] = []

        if PSD_TOOLS_AVAILABLE and PIL_AVAILABLE and self._psd_path:
            try:
                psd = PSDImage.open(str(self._psd_path))
                needed_names = {name for (name, _p, _b) in self._so_layers}

                for layer in self._iter_psd_layers(psd):
                    try:
                        if layer.name not in needed_names:
                            continue

                        img = None
                        try:
                            img = layer.composite(force=True)
                        except Exception:
                            pass
                        if img is None:
                            try:
                                img = layer.topil()
                            except Exception:
                                img = None
                        if img is None:
                            continue

                        w, h = img.size
                        thumb = img.copy()
                        thumb.thumbnail(self.THUMB_SIZE, Image.Resampling.LANCZOS)
                        collected.append((layer.name, w, h, thumb))
                    except Exception as e:
                        print(f"[SOPicker] layer '{getattr(layer, 'name', '?')}' skipped: {e}")
                        continue
            except Exception as e:
                print(f"[SOPicker] psd-tools open failed: {e}")

        # Матчинг: каждой карточке — своё превью (по имени, ближайший размер)
        used = [False] * len(collected)

        def _match(name: str, tw: int, th: int):
            best_i = -1
            best_score = float("inf")
            for i, (cn, cw, ch, _img) in enumerate(collected):
                if used[i] or cn != name:
                    continue
                score = abs(cw - tw) + abs(ch - th)
                if score < best_score:
                    best_score = score
                    best_i = i
            if best_i >= 0:
                used[best_i] = True
                return collected[best_i][3]
            return None

        # Строим сетку
        for i, (name, path_key, bounds) in enumerate(self._so_layers):
            r = i // self.COLUMNS
            c = i % self.COLUMNS
            try:
                tw = int(bounds[2] - bounds[0])
                th = int(bounds[3] - bounds[1])
            except Exception:
                tw = th = 0
            thumb = _match(name, tw, th)
            self._build_card(
                self._grid_frame, r, c, i, name, path_key, bounds, thumb,
            )

        for c in range(self.COLUMNS):
            self._grid_frame.columnconfigure(c, weight=1)

    def _build_card(
        self,
        parent: tk.Widget,
        row: int,
        col: int,
        idx: int,
        name: str,
        path_key: list,
        bounds: tuple,
        thumb: Optional["Image.Image"],
    ) -> None:
        cell = ttk.Frame(parent, padding=8, relief="ridge", borderwidth=1)
        cell.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

        if thumb is not None and PIL_AVAILABLE:
            bg = Image.new("RGBA", self.THUMB_SIZE, (60, 60, 60, 255))
            px = (self.THUMB_SIZE[0] - thumb.width) // 2
            py = (self.THUMB_SIZE[1] - thumb.height) // 2
            if thumb.mode == "RGBA":
                bg.paste(thumb, (px, py), thumb)
            else:
                bg.paste(thumb, (px, py))
            photo = ImageTk.PhotoImage(bg)
            self._photo_refs[idx] = photo
            lbl = tk.Label(cell, image=photo, bg="#3b3b3b")
        else:
            lbl = tk.Label(
                cell,
                text="[превью недоступно]",
                width=22, height=8,
                bg="#3b3b3b", fg="#aaa",
            )
        lbl.pack()

        try:
            w = int(bounds[2] - bounds[0])
            h = int(bounds[3] - bounds[1])
        except Exception:
            w = h = 0
        info = ttk.Label(cell, text=f"{name}\n{w}×{h} px", justify="center")
        info.pack(pady=(6, 4))

        btn = ttk.Button(
            cell, text="Заменить",
            command=lambda n=name, p=path_key: self._pick_and_replace(n, p),
        )
        btn.pack()

    @staticmethod
    def _iter_psd_layers(psd):
        """Итерация по всем слоям PSD рекурсивно (psd-tools)."""
        def walk(container):
            for L in container:
                yield L
                try:
                    if L.is_group():
                        yield from walk(L)
                except Exception:
                    pass
        yield from walk(psd)

    def _pick_and_replace(self, name: str, path_key: list) -> None:
        img_path = filedialog.askopenfilename(
            parent=self,
            title=f"Фото для '{name}'",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.tif *.tiff *.bmp"), ("All", "*.*")],
        )
        if not img_path:
            return
        try:
            self._on_replace(name, path_key, img_path)
        finally:
            self.destroy()
