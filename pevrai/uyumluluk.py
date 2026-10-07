"""Read existing installations without moving personal files or changing permissions."""
from __future__ import annotations

import os
from pathlib import Path


def ortam(sonek: str, varsayilan: str | None = None) -> str | None:
    """Prefer the new environment namespace, including explicitly empty values."""
    return os.environ.get("PEVRAI_" + sonek,
                          os.environ.get("LIMINA_" + sonek, varsayilan))


def veri_koku(yerel: Path) -> Path:
    """New installations use Pevrai; existing installations retain their data."""
    yeni = yerel / "Pevrai"
    eski = yerel / "Limina"
    if any((yeni / name).is_file() for name in
           ("policy.toml", "config/arayuz.toml", "config/persona.md")):
        return yeni
    return eski if eski.is_dir() else yeni
