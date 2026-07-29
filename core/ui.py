"""Градиентные UI-хелперы и компоненты для Prizma Studio (Pillow -> CTkImage).

Поддержка 3-стоп градиента: c1 -> c2 -> c3 (бирюза -> индиго -> фиолет).
Совместимо со старой сигнатурой (c2 обязателен, c3 опционален).
"""
from __future__ import annotations

import customtkinter as ctk

try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = None
    ImageDraw = None


def _hex(c: str):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _lerp(a, b, t):
    return int(a + (b - a) * t)


def grad_ctkimage(w: int, h: int, c1: str, c2: str, c3: str | None = None,
                  radius: int = 0):
    """Горизонтальный градиент c1 -> [c2 ->] c3 с опциональным скруглением."""
    if Image is None:
        return None
    w = max(1, int(w)); h = max(1, int(h))

    if c3 is None:
        stops = [_hex(c1), _hex(c2)]
    else:
        stops = [_hex(c1), _hex(c2), _hex(c3)]

    row = Image.new("RGB", (w, 1))
    px = row.load()
    n = len(stops) - 1
    for x in range(w):
        t = x / (w - 1) if w > 1 else 0
        seg = min(int(t * n), n - 1)
        local_t = t * n - seg
        (r1, g1, b1) = stops[seg]
        (r2, g2, b2) = stops[seg + 1]
        px[x, 0] = (_lerp(r1, r2, local_t),
                    _lerp(g1, g2, local_t),
                    _lerp(b1, b2, local_t))
    grad = row.resize((w, h)).convert("RGBA")

    if radius > 0 and ImageDraw is not None:
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1],
                                               radius=radius, fill=255)
        grad.putalpha(mask)

    return ctk.CTkImage(light_image=grad, dark_image=grad, size=(w, h))


def solid_ctkimage(w: int, h: int, color: str, radius: int = 0):
    if Image is None:
        return None
    w = max(1, int(w)); h = max(1, int(h))
    img = Image.new("RGBA", (w, h), _hex(color) + (255,))
    if radius > 0 and ImageDraw is not None:
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1],
                                               radius=radius, fill=255)
        img.putalpha(mask)
    return ctk.CTkImage(light_image=img, dark_image=img, size=(w, h))


class GradientDivider(ctk.CTkLabel):
    """Тонкая горизонтальная линия-градиент во всю ширину."""

    def __init__(self, master, c1: str, c2: str, c3: str | None = None,
                 height: int = 2):
        super().__init__(master, text="", height=height)
        self._c1, self._c2, self._c3 = c1, c2, c3
        self._height_px = height
        self._after = None
        self._img = None
        self._last_w = 0
        self.bind("<Configure>", self._on_cfg)

    def _on_cfg(self, event):
        if event.width <= 1 or event.width == self._last_w:
            return
        self._last_w = event.width
        if self._after:
            self.after_cancel(self._after)
        self._after = self.after(80, lambda w=event.width: self._render(w))

    def _render(self, w: int):
        img = grad_ctkimage(w, self._height_px, self._c1, self._c2, self._c3, radius=0)
        if img:
            self._img = img
            self.configure(image=img)


class NavButton(ctk.CTkFrame):
    """Пункт бокового меню с профессиональным видом.

    Состояния:
      - неактивный: прозрачный фон, серый текст/иконка;
      - hover: лёгкая подсветка фона;
      - активный: тонкий вертикальный акцент-бар слева + мягкая подложка +
        белый текст/иконка.
    """

    _ICON_FONT_CANDIDATES = (
        "Segoe Fluent Icons",
        "Segoe MDL2 Assets",
    )

    def __init__(self, master, text: str, c1: str, c2: str,
                 c3: str | None = None,
                 icon: str = "",
                 width: int = 216, height: int = 42, command=None,
                 inactive_color: str = "#A0AABA",
                 active_bg: str = "#1A1F29",
                 hover_bg: str = "#161A22",
                 **kw):
        super().__init__(master, width=width, height=height,
                         fg_color="transparent", corner_radius=10,
                         border_width=0)
        self.grid_propagate(False)
        self.pack_propagate(False)

        self._c1, self._c2, self._c3 = c1, c2, c3
        self._width_px, self._height_px = width, height
        self._inactive = inactive_color
        self._active_bg = active_bg
        self._hover_bg = hover_bg
        self._command = command
        self._active = False

        # Левый акцент-бар (виден только когда активен)
        self._bar_img_active = None
        self._bar = ctk.CTkLabel(self, text="", width=3, height=height - 12)
        self._bar.place(x=0, y=6)

        # Иконка
        icon_font = self._resolve_icon_font()
        self._icon = ctk.CTkLabel(
            self, text=icon, width=28, height=height,
            font=(icon_font, 16),
            text_color=inactive_color,
            fg_color="transparent",
        )
        self._icon.place(x=14, y=0)

        # Текст
        self._label = ctk.CTkLabel(
            self, text=text, height=height,
            font=("Segoe UI Semibold", 13),
            text_color=inactive_color,
            anchor="w", fg_color="transparent",
        )
        self._label.place(x=48, y=0, relwidth=1, width=-56)

        # Клики / hover
        for w in (self, self._icon, self._label):
            w.bind("<Button-1>", self._on_click)
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
            try:
                w.configure(cursor="hand2")
            except Exception:
                pass

    # ------------------------------------------------------------------
    def _resolve_icon_font(self) -> str:
        try:
            import tkinter.font as tkfont
            families = set(tkfont.families())
            for f in self._ICON_FONT_CANDIDATES:
                if f in families:
                    return f
        except Exception:
            pass
        return "Segoe UI"

    def _ensure_bar(self):
        if self._bar_img_active is None:
            self._bar_img_active = grad_ctkimage(
                3, self._height_px - 12, self._c1, self._c2, self._c3, radius=2
            )

    # ------------------------------------------------------------------
    def set_text(self, text: str):
        self._label.configure(text=text)

    def set_icon(self, icon: str):
        self._icon.configure(text=icon)

    def configure(self, **kwargs):
        if "text" in kwargs:
            self._label.configure(text=kwargs.pop("text"))
        if kwargs:
            super().configure(**kwargs)

    def set_active(self, active: bool):
        self._active = bool(active)
        if self._active:
            self._ensure_bar()
            if self._bar_img_active is not None:
                self._bar.configure(image=self._bar_img_active)
            super().configure(fg_color=self._active_bg)
            self._icon.configure(text_color="#FFFFFF", fg_color=self._active_bg)
            self._label.configure(text_color="#FFFFFF", fg_color=self._active_bg)
        else:
            self._bar.configure(image="")
            super().configure(fg_color="transparent")
            self._icon.configure(text_color=self._inactive, fg_color="transparent")
            self._label.configure(text_color=self._inactive, fg_color="transparent")

    # ------------------------------------------------------------------
    def _on_click(self, _event=None):
        if callable(self._command):
            self._command()

    def _on_enter(self, _event=None):
        if self._active:
            return
        super().configure(fg_color=self._hover_bg)
        self._icon.configure(fg_color=self._hover_bg, text_color="#D6DBE3")
        self._label.configure(fg_color=self._hover_bg, text_color="#D6DBE3")

    def _on_leave(self, _event=None):
        if self._active:
            return
        super().configure(fg_color="transparent")
        self._icon.configure(fg_color="transparent", text_color=self._inactive)
        self._label.configure(fg_color="transparent", text_color=self._inactive)
