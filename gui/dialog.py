"""GTK dialog: the GUI adapter.

Collects Title/Name/Theme/Date input, builds a ThumbnailRequest, and
delegates all image editing/export work to core.service/core.export. This
module must not contain layer-selection, fallback, or export logic itself
(see AGENT/plans/refactoring.md §25).
"""

from __future__ import annotations

import datetime
import logging
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gimp, Gtk

from core import export, layers, service, title
from core.config import PluginConfig
from core.models import PluginError, ThumbnailRequest

logger = logging.getLogger(__name__)

_RESPONSE_PREVIEW = 1
_RESPONSE_EXPORT = 2


def run_dialog(image, config: PluginConfig) -> None:
    name_options = layers.discover_by_prefix(image, config.image_prefix)
    theme_options = layers.discover_by_prefix(image, config.series_prefix)

    if not name_options or not theme_options:
        Gimp.message(
            "Fehlende Layer.\nStelle sicher, dass es mindestens je eine Layer "
            f"gibt, die mit '{config.image_prefix}' (Bild) sowie mit "
            f"'{config.series_prefix}' (Hintergrund) beginnt."
        )
        return

    dialog = Gtk.Dialog(title="Stream-Thumbnail aktualisieren", flags=Gtk.DialogFlags.MODAL)
    dialog.add_button("_Cancel", Gtk.ResponseType.CANCEL)
    dialog.add_button("_Preview", _RESPONSE_PREVIEW)
    dialog.add_button("_Export", _RESPONSE_EXPORT)

    content = dialog.get_content_area()

    title_label = Gtk.Label(label="Predigt-Titel:")
    title_view = Gtk.TextView()
    title_view.set_wrap_mode(Gtk.WrapMode.WORD)
    title_scroller = Gtk.ScrolledWindow()
    title_scroller.set_min_content_height(80)
    title_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    title_scroller.add(title_view)
    _prefill_title(image, config, title_view.get_buffer())

    name_label = Gtk.Label(label="Prediger:")
    name_combo = Gtk.ComboBoxText()
    for name in name_options:
        name_combo.append_text(name)
    _select_currently_visible(name_combo, image, config.image_prefix, name_options)

    theme_label = Gtk.Label(label="Predigt-Reihe:")
    theme_combo = Gtk.ComboBoxText()
    for theme_name in theme_options:
        theme_combo.append_text(theme_name)
    _select_currently_visible(theme_combo, image, config.series_prefix, theme_options)

    date_label = Gtk.Label(label="Datum:")
    date_entry = Gtk.Entry()
    date_entry.set_text(datetime.date.today().isoformat())
    date_entry.set_placeholder_text("YYYY-MM-DD")

    grid = Gtk.Grid(column_spacing=8, row_spacing=8)
    grid.attach(title_label, 0, 0, 1, 1)
    grid.attach(title_scroller, 1, 0, 1, 1)
    grid.attach(name_label, 0, 1, 1, 1)
    grid.attach(name_combo, 1, 1, 1, 1)
    grid.attach(theme_label, 0, 2, 1, 1)
    grid.attach(theme_combo, 1, 2, 1, 1)
    grid.attach(date_label, 0, 3, 1, 1)
    grid.attach(date_entry, 1, 3, 1, 1)

    content.add(grid)
    dialog.show_all()

    try:
        while True:
            response = dialog.run()
            if response in (Gtk.ResponseType.CANCEL, Gtk.ResponseType.DELETE_EVENT):
                break
            if response not in (_RESPONSE_PREVIEW, _RESPONSE_EXPORT):
                continue

            try:
                request = _build_request(title_view, name_combo, theme_combo, date_entry)
                service.generate_thumbnail(image, request, config)
                if response == _RESPONSE_EXPORT:
                    output_path = _export(image, config, request)
                    Gimp.message(f"Exportiert nach:\n{output_path}")
            except PluginError as exc:
                Gimp.message(str(exc))
            except Exception as exc:
                # Keep the dialog open even on an unexpected/programming error —
                # crashing the whole modal loop over one bad click is worse.
                logger.exception("Unexpected error handling response %s", response)
                Gimp.message(f"Unerwarteter Fehler:\n{exc}")
    finally:
        dialog.destroy()


def _prefill_title(image, config: PluginConfig, buffer: Gtk.TextBuffer) -> None:
    title_layer = layers.find_text_layer_by_name(image, config.title_layer_name)
    if title_layer is None:
        return
    try:
        buffer.set_text(title_layer.get_text())
    except Exception:
        logger.warning("Could not read current title text from %s", config.title_layer_name, exc_info=True)


def _select_currently_visible(combo: Gtk.ComboBoxText, image, prefix: str, options: list[str]) -> None:
    active_index = 0
    for index, name in enumerate(options):
        layer = layers.find_layer_by_name(image, prefix + name)
        if layer is not None and layer.get_visible():
            active_index = index
            break
    combo.set_active(active_index)


def _build_request(title_view: Gtk.TextView, name_combo, theme_combo, date_entry) -> ThumbnailRequest:
    buffer = title_view.get_buffer()
    raw_title = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)

    name = name_combo.get_active_text()
    theme = theme_combo.get_active_text()
    if name is None or theme is None:
        raise PluginError("Bitte Prediger und Predigt-Reihe auswählen.")

    date_text = export.parse_date(date_entry.get_text().strip())

    return ThumbnailRequest(
        title=title.simple_richtext(raw_title),
        name=name,
        theme=theme,
        date=date_text,
    )


def _export(image, config: PluginConfig, request: ThumbnailRequest) -> Path:
    template_file = image.get_file()
    if template_file is None or template_file.get_path() is None:
        raise PluginError(
            "Kann den Speicherort der Vorlage nicht bestimmen.\n"
            "Bitte die Vorlage zunächst als Datei speichern."
        )
    template_path = Path(template_file.get_path())
    output_path = export.build_output_path(config, template_path, request.date, request.title)
    return export.export_png(image, output_path)
