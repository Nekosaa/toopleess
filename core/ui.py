"""Градиентные UI-хелперы и компоненты для Prizma Studio (Pillow -> CTkImage)."""
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


def grad_ctkimage(w: int, h: int, c1: str, c2: str, radius: int = 0):
    """Горизонтальный градиент c1->c2 с опциональным скруглением углов."""
    if Image is None:
        return None
    w = max(1, int(w)); h = max(1, int(h))
    r1, g1, b1 = _hex(c1); r2, g2, b2 = _hex(c2)

    row = Image.new("RGB", (w, 1))
    px = row.load()
    for x in range(w):
        t = x / (w - 1) if w > 1 else 0
        px[x, 0] = (int(r1 + (r2 - r1) * t),
                    int(g1 + (g2 - g1) * t),
                    int(b1 + (b2 - b1) * t))
    grad = row.resize((w, h)).convert("RGBA")

    if radius > 0 and ImageDraw is not None:
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1],
                                               radius=radius, fill=255)
        grad.putalpha(mask)

    return ctk.CTkImage(light_image=grad, dark_image=grad, size=(w, h))


class GradientDivider(ctk.CTkLabel):
    """Тонкая горизонтальная линия-градиент во всю ширину."""

    def __init__(self, master, c1: str, c2: str, height: int = 3):
        super().__init__(master, text="", height=height)
        self._c1, self._c2, self._grad_h = c1, c2, height
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
        # ВАЖНО: имя _render, а не _draw (последнее занято customtkinter)
        self._after = self.after(80, lambda w=event.width: self._render(w))

    def _render(self, w: int):
        img = grad_ctkimage(w, self._grad_h, self._c1, self._c2, radius=0)
        if img:
            self._img = img
            self.configure(image=img)


class NavButton(ctk.CTkButton):
    """Пункт бокового меню: прозрачный по умолчанию, градиентная «пилюля» когда активен."""

    def __init__(self, master, text: str, c1: str, c2: str,
                 width: int = 208, height: int = 44, command=None,
                 inactive_color: str = "#9AA0AE", hover_color: str = "#1E1F27", **kw):
        super().__init__(
            master, text=text, width=width, height=height, corner_radius=12,
            fg_color="transparent", hover_color=hover_color,
            text_color=inactive_color, font=("Segoe UI Semibold", 13),
            command=command, **kw,
        )
        self._c1, self._c2 = c1, c2
        self._grad_w, self._grad_h = width, height
        self._inactive = inactive_color
        self._img = None

    def _ensure_img(self):
        if self._img is None:
            self._img = grad_ctkimage(self._grad_w, self._grad_h, self._c1, self._c2, radius=12)

    def set_active(self, active: bool):
        if active:
            self._ensure_img()
            if self._img is not None:
                self.configure(image=self._img, compound="center")
            self.configure(text_color="#FFFFFF")
        else:
            self.configure(image=None, text_color=self._inactive)
