"""Application service: the one place GUI and CLI both call to apply a
ThumbnailRequest to an already-open template image.

Export is a separate, later step (core/export.py) — this module only
performs the in-image edits (title, label, box, layer visibility), matching
the plugin's original GUI-only behavior. See AGENT/plans/refactoring.md §4a.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from . import layers, title
from .config import PluginConfig
from .models import PluginError, ThumbnailRequest, ThumbnailResult


@dataclass
class GimpRuntime:
    pixel_unit: object
    channel_replace: object
    fill_foreground: object
    black_color: object
    set_foreground: Callable[[object], None]
    clear_selection: Callable[[object], None]
    flush_displays: Callable[[], None]


def default_runtime() -> GimpRuntime:
    from gi.repository import Gegl, Gimp

    return GimpRuntime(
        pixel_unit=Gimp.Unit.pixel(),
        channel_replace=Gimp.ChannelOps.REPLACE,
        fill_foreground=Gimp.FillType.FOREGROUND,
        black_color=Gegl.Color.new("black"),
        set_foreground=Gimp.context_set_foreground,
        clear_selection=Gimp.Selection.none,
        flush_displays=Gimp.displays_flush,
    )


def generate_thumbnail(
    image,
    request: ThumbnailRequest,
    config: PluginConfig,
    runtime: GimpRuntime | None = None,
) -> ThumbnailResult:
    runtime = runtime or default_runtime()

    title_layer = layers.find_text_layer_by_name(image, config.title_layer_name)
    box_layer = layers.find_layer_by_name(image, config.title_box_layer_name)
    label_layer = layers.find_text_layer_by_name(image, config.label_layer_name)

    missing = [
        name
        for layer, name in (
            (title_layer, config.title_layer_name),
            (box_layer, config.title_box_layer_name),
            (label_layer, config.label_layer_name),
        )
        if layer is None
    ]
    if missing:
        raise PluginError("Required layers are missing:\n" + "\n".join(missing))

    title_plain = "".join(run.text for run in request.title.runs)
    if title_plain != "":
        title.render(title_layer, request.title, config.default_title_size, unit=runtime.pixel_unit)

    label_layer.set_font_size(config.default_name_size, runtime.pixel_unit)
    label_layer.set_text(request.name)

    _redraw_title_box(image, title_layer, box_layer, config, runtime)

    layers.reset_visibility(image, config.image_prefix, config.default_image_layer_name)
    layers.reset_visibility(image, config.series_prefix, config.default_series_layer_name)

    name_layer, used_name_fallback = layers.select_with_fallback(
        image, config.image_prefix, request.name, config.default_image_layer_name
    )
    theme_layer, used_theme_fallback = layers.select_with_fallback(
        image, config.series_prefix, request.theme, config.default_series_layer_name
    )
    name_layer.set_visible(True)
    theme_layer.set_visible(True)

    runtime.flush_displays()
    runtime.clear_selection(image)

    return ThumbnailResult(
        output_path=None,
        selected_name=request.name,
        selected_theme=request.theme,
        used_name_fallback=used_name_fallback,
        used_theme_fallback=used_theme_fallback,
    )


def _redraw_title_box(image, title_layer, box_layer, config: PluginConfig, runtime: GimpRuntime) -> None:
    runtime.flush_displays()
    w, h = title_layer.get_width(), title_layer.get_height()
    pad_top, pad_bottom, pad_side = config.box_padding
    anchor_x, anchor_y = config.title_anchor

    title_layer.set_offsets(int(anchor_x - w / 2), int(anchor_y - h / 2))

    offset_success, x, y = title_layer.get_offsets()
    if not offset_success:
        x, y = 0, 0

    try:
        box_x, box_y = box_layer.get_offsets()[1:]
        box_w, box_h = box_layer.get_width(), box_layer.get_height()
        image.select_rectangle(runtime.channel_replace, float(box_x), float(box_y), float(box_w), float(box_h))
        box_layer.edit_clear()

        image.select_rectangle(
            runtime.channel_replace,
            float(x - pad_side),
            float(y - pad_top),
            float(w + 2 * pad_side),
            float(h + pad_top + pad_bottom),
        )
        runtime.set_foreground(runtime.black_color)
        box_layer.edit_fill(runtime.fill_foreground)
    finally:
        runtime.clear_selection(image)
