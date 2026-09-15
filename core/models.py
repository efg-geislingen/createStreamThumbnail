from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


class PluginError(Exception):
    pass


@dataclass
class TextRun:
    text: str
    font: str | None = None
    size: float | None = None
    bold: bool | None = None
    italic: bool | None = None


@dataclass
class RichText:
    runs: list[TextRun] = field(default_factory=list)


@dataclass
class ThumbnailRequest:
    title: RichText
    name: str
    theme: str
    date: str


@dataclass
class ThumbnailResult:
    output_path: Path | None
    selected_name: str
    selected_theme: str
    used_name_fallback: bool
    used_theme_fallback: bool
