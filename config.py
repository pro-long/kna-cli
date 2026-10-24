"""
Config management for KnaCLI.
Stores user preferences in ~/.config/knacli/config.json
"""

import json
from pathlib import Path

DEFAULT_CONFIG = {
    "download_path": "/storage/emulated/0/Downloads/torrent_downloads",
    "default_sort": "seeders",
    "default_results": 50,
    "aria2c_path": "aria2c",
}

CONFIG_DIR = Path.home() / ".config" / "knacli"
CONFIG_FILE = CONFIG_DIR / "config.json"


class Config:
    """Persistent config backed by a JSON file."""

    def __init__(self):
        self._data: dict = DEFAULT_CONFIG.copy()
        self._load()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self._data.update(loaded)
            except (json.JSONDecodeError, IOError):
                pass  # silently fall back to defaults

    def _save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    # ------------------------------------------------------------------
    # Generic get / set
    # ------------------------------------------------------------------

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value
        self._save()

    # ------------------------------------------------------------------
    # Typed properties
    # ------------------------------------------------------------------

    @property
    def download_path(self) -> str:
        return self._data.get("download_path", DEFAULT_CONFIG["download_path"])

    @download_path.setter
    def download_path(self, value: str) -> None:
        self._data["download_path"] = value
        self._save()

    @property
    def default_sort(self) -> str:
        return self._data.get("default_sort", "seeders")

    @property
    def default_results(self) -> int:
        return int(self._data.get("default_results", 50))

    @property
    def aria2c_path(self) -> str:
        return self._data.get("aria2c_path", "aria2c")
