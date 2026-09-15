"""PNG export: output path/filename derivation (pure, gi-free) and the
actual GIMP export call (needs gi, imported lazily).

Verified against the installed GIMP 3.2.2 Python bindings:
`Gimp.file_save(run_mode, image, file, options=None) -> bool`,
`Gimp.Image.duplicate() -> Image`, `Gimp.Image.flatten() -> Layer`.
"""

from __future__ import annotations

import re
from datetime import date as _date
from pathlib import Path

from .config import PluginConfig
from .models import PluginError, RichText

_INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')


def parse_date(date_str: str) -> str:
    try:
        _date.fromisoformat(date_str)
    except ValueError as exc:
        raise PluginError(f"Invalid date '{date_str}', expected YYYY-MM-DD.") from exc
    return date_str


def title_to_filename_part(title: RichText) -> str:
    plain = "".join(run.text for run in title.runs).replace("\n", " ")
    sanitized = _INVALID_FILENAME_CHARS.sub("_", plain)
    return sanitized.strip(" .")


def build_output_path(config: PluginConfig, template_path: Path, date: str, title: RichText) -> Path:
    parse_date(date)
    title_part = title_to_filename_part(title)
    return template_path.parent / config.output_subdir / f"{date}_{title_part}.png"


def export_png(image, output_path: Path) -> Path:
    """Exports a flattened copy of `image` as a PNG, never mutating `image`
    itself — the caller's open/live image (and its layer structure) is left
    untouched, per AGENT/plans/refactoring.md §29/§4b.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    from gi.repository import Gimp, Gio

    export_image = image.duplicate()
    try:
        export_image.flatten()
        destination = Gio.File.new_for_path(str(output_path))
        succeeded = Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, export_image, destination, None)
    finally:
        export_image.delete()

    if not succeeded or not output_path.exists():
        raise PluginError(f"Could not export PNG to:\n{output_path}")

    return output_path
