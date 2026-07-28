"""Градиентные UI-хелперы для Prizma Studio (Pillow -> CTkImage)."""
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
        self._c1, self._c2, self._h = c1, c2, height
        self._after = None
        self._img = None
        self.bind("<Configure>", self._on_cfg)

    def _on_cfg(self, event):
        if self._after:
            self.after_cancel(self._after)
        self._after = self.after(100, lambda w=event.width: self._draw(w))

    def _draw(self, w: int):
        img = grad_ctkimage(w, self._h, self._c1, self._c2, radius=0)
        if img:
            self._img = img
            self.configure(image=img)
