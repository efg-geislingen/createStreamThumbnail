"""Title parsing and rendering.

`normalize_newlines`, `simple_richtext` and `parse_title_json` are pure and
gi-free. `render` needs a GIMP unit constant to call `set_font_size`; it
accepts one via the optional `unit` parameter (lazily resolved to the real
`Gimp.Unit.pixel()` when omitted) so the plain-text path can be exercised in
tests with a fake text layer and a dummy unit value, without importing `gi`.

Multi-run/styled titles render via `Gimp.TextLayer.set_markup()` (Pango
markup) — confirmed available on GIMP 3.2.2. Empirically verified against
GIMP's real Pango bindings (`Pango.parse_markup`) that the `size` span
attribute must be a plain integer in 1024ths of a point — no unit-suffixed
value like "64px" is accepted — so an explicit per-run pixel size is
converted to points using the layer's image resolution before being placed
in markup. A run that leaves font/size/bold/italic unset emits no `<span>`
at all, so it inherits the layer's base font exactly as set by
`set_font_size`/the template's own font, per
AGENT/plans/refactoring.md §6.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import PluginError, RichText, TextRun

_PANGO_SCALE = 1024


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def simple_richtext(text: str) -> RichText:
    return RichText(runs=[TextRun(text=normalize_newlines(text))])


def parse_title_json(source: str) -> RichText:
    """Parses the structured `{"runs": [...]}` title format.

    `source` is either an inline JSON string, or a path to a file
    containing it.
    """
    stripped = source.strip()
    if stripped.startswith("{"):
        raw = stripped
    else:
        path = Path(source)
        if not path.is_file():
            raise PluginError(f"Rich-text JSON file not found:\n{path}")
        raw = path.read_text(encoding="utf-8")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PluginError(f"Invalid rich-text JSON: {exc}") from exc

    if not isinstance(data, dict) or not isinstance(data.get("runs"), list) or not data["runs"]:
        raise PluginError("Invalid rich-text JSON: expected an object with a non-empty 'runs' array.")

    runs = []
    for index, run_data in enumerate(data["runs"]):
        if not isinstance(run_data, dict) or "text" not in run_data:
            raise PluginError(f"Invalid rich-text JSON: run {index} is missing 'text'.")
        runs.append(TextRun(
            text=normalize_newlines(str(run_data["text"])),
            font=run_data.get("font"),
            size=run_data.get("size"),
            bold=run_data.get("bold"),
            italic=run_data.get("italic"),
        ))
    return RichText(runs=runs)


def _is_plain(richtext: RichText) -> bool:
    """True if this title needs no per-character markup at all.

    A single run may still set an explicit `size` and use the plain
    `set_text`/`set_font_size` path — it applies uniformly to the whole
    layer, no different from the layer's existing font size. Only
    font/bold/italic actually require per-character Pango markup.
    """
    if len(richtext.runs) != 1:
        return False
    run = richtext.runs[0]
    return not (run.font or run.bold or run.italic)


def _escape_text(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _escape_attr(value: str) -> str:
    return _escape_text(value).replace('"', "&quot;")


def _pango_size_attr(size_px: float, text_layer) -> int:
    xres = 72.0
    try:
        success, resolution_x, _ = text_layer.get_image().get_resolution()
        if success and resolution_x:
            xres = resolution_x
    except Exception:
        pass
    points = size_px * 72.0 / xres
    return round(points * _PANGO_SCALE)


def _run_to_markup(run: TextRun, text_layer) -> str:
    attrs = []
    if run.font:
        attrs.append(f'font_family="{_escape_attr(run.font)}"')
    if run.size is not None:
        attrs.append(f'size="{_pango_size_attr(run.size, text_layer)}"')
    if run.bold:
        attrs.append('font_weight="bold"')
    if run.italic:
        attrs.append('font_style="italic"')

    text = _escape_text(run.text)
    if not attrs:
        return text
    return f'<span {" ".join(attrs)}>{text}</span>'


def render(text_layer, richtext: RichText, default_size: float, unit=None) -> None:
    if unit is None:
        from gi.repository import Gimp

        unit = Gimp.Unit.pixel()

    if _is_plain(richtext):
        run = richtext.runs[0]
        text_layer.set_font_size(run.size if run.size is not None else default_size, unit)
        text_layer.set_text(run.text)
        return

    text_layer.set_font_size(default_size, unit)
    markup = "".join(_run_to_markup(run, text_layer) for run in richtext.runs)
    text_layer.set_markup(markup)
