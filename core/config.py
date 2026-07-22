"""Application configuration – persisted at ~/.tools_config.json."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONFIG_PATH = Path.home() / ".tools_config.json"

DEFAULTS: dict[str, Any] = {
    "language": "ru",           # ru | en
    "theme": "system",          # system | light | dark
    "pdf_last_dir": str(Path.home()),
    "psd_in_dir": str(Path.home()),
    "psd_out_dir": str(Path.home()),
    "smart_object_depth": 3,
    "window_geometry": "1200x760",
}


class Config:
    """Thin wrapper over a JSON file with dict-like access."""

    def __init__(self, path: Path = CONFIG_PATH) -> None:
        self._path = path
        self._data: dict[str, Any] = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        if self._path.exists():
            try:
                with self._path.open("r", encoding="utf-8") as fh:
                    saved = json.load(fh)
                if isinstance(saved, dict):
                    self._data.update({k: v for k, v in saved.items() if k in DEFAULTS})
            except (OSError, json.JSONDecodeError):
                pass

    def save(self) -> None:
        try:
            with self._path.open("w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, ensure_ascii=False)
        except OSError:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()

    def update(self, **kwargs: Any) -> None:
        self._data.update(kwargs)
        self.save()

    def as_dict(self) -> dict[str, Any]:
        return dict(self._data)


# Singleton – all tabs share the same config instance.
config = Config()
