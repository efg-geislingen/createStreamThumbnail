#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Stream Thumbnail Helper

# ─────────────────────────────────────────────
# TODO
# ─────────────────────────────────────────────
"""
- Deactivate OK/Preview/Export buttons until all inputs have values
- Set Title Box to size of each text line individually
"""

# ─────────────────────────────────────────────
# IMPORTS
# ─────────────────────────────────────────────

import os
import sys

# Ensure sibling packages (core/, gui/) resolve regardless of how GIMP
# invokes this script.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Imports may appear broken in IDE, but will work in GIMP
import gi

gi.require_version("Gimp", "3.0")
from gi.repository import Gimp

gi.require_version("GimpUi", "3.0")
from gi.repository import Gio, GimpUi
from gi.repository import GObject
from gi.repository import GLib

from pathlib import Path

from core import export, service, title
from core.config import PluginConfig
from core.models import PluginError, ThumbnailRequest
from gui.dialog import run_dialog

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

CONFIG = PluginConfig()

GUI_PROC_NAME = "python-fu-stream-thumbnail-helper"
BATCH_PROC_NAME = "python-fu-stream-thumbnail-batch"


def _unexpected_error_return(procedure, exc: Exception):
    import traceback

    Gimp.message("Unexpected error:\n" + str(exc) + "\n" + traceback.format_exc())
    return procedure.new_return_values(
        Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error(str(exc))
    )


# ─────────────────────────────────────────────
# MAIN PLUGIN CLASS
# ─────────────────────────────────────────────

class StreamThumbnailHelper(Gimp.PlugIn):
    def do_set_i18n(self, procedure_name):
        # No translations shipped; skip GIMP's default locale/ directory
        # lookup (and its "catalog directory does not exist" log noise).
        return False, None, None

    def do_query_procedures(self):
        return [GUI_PROC_NAME, BATCH_PROC_NAME]

    def do_create_procedure(self, name):
        if name == GUI_PROC_NAME:
            return self._create_gui_procedure(name)
        if name == BATCH_PROC_NAME:
            return self._create_batch_procedure(name)
        return None

    def _create_gui_procedure(self, name):
        proc = Gimp.ImageProcedure.new(
            self,
            name,
            Gimp.PDBProcType.PLUGIN,
            self.run,
            None
        )

        # Plugin stuff
        proc.set_menu_label("Stream-Thumbnail aktualisieren...")
        proc.set_attribution("NAME", "NAME, INSTITUTION", "2025")
        proc.add_menu_path("<Image>/EFG Plugins")

        proc.set_documentation(
            "Aktualisiert Titel, Prediger, Bild und Drop-Shadow",
            "Dynamisches Stream-Thumbnail-Tool",
            None
        )

        # Plugin arguments
        proc.add_image_argument(
            "image",
            "Input image",
            "blurrbbbb",
            False,
            GObject.ParamFlags.READWRITE
        )
        proc.add_drawable_argument(
            "drawable",
            "Input drawable",
            "mehr blurrbbb",
            False,
            GObject.ParamFlags.READWRITE
        )

        return proc

    def _create_batch_procedure(self, name):
        proc = Gimp.Procedure.new(
            self,
            name,
            Gimp.PDBProcType.PLUGIN,
            self.run_batch,
            None
        )

        proc.set_attribution("NAME", "NAME, INSTITUTION", "2025")
        proc.set_documentation(
            "Erstellt ein Stream-Thumbnail ohne GUI (Batch/CLI)",
            "Non-interactive counterpart of " + GUI_PROC_NAME + ": loads a "
            "template, applies title/name/theme via the same core logic, "
            "and exports a PNG. Never modifies the template file itself.",
            None
        )

        proc.add_string_argument(
            "template", "Template path", "Path to the .xcf template", "",
            GObject.ParamFlags.READWRITE
        )
        proc.add_string_argument(
            "title", "Title",
            "Plain title text (use \\n for line breaks); ignored if title-json is non-empty",
            "", GObject.ParamFlags.READWRITE
        )
        proc.add_string_argument(
            "title-json", "Title JSON",
            "Structured rich-text title: inline JSON or a path to a .json file",
            "", GObject.ParamFlags.READWRITE
        )
        proc.add_string_argument(
            "theme", "Theme",
            "Requested Predigt-Reihe (falls back to the configured default if not found)",
            "", GObject.ParamFlags.READWRITE
        )
        proc.add_string_argument(
            "name", "Name",
            "Requested Prediger (falls back to the configured default if not found)",
            "", GObject.ParamFlags.READWRITE
        )
        proc.add_string_argument(
            "date", "Date", "YYYY-MM-DD, used for the export filename", "",
            GObject.ParamFlags.READWRITE
        )
        proc.add_string_argument(
            "output", "Output path",
            "Optional: full file path or directory, overriding the default output/ subfolder next to the template",
            "", GObject.ParamFlags.READWRITE
        )

        return proc

    # ─────────────────────────────────────────────
    # RUN (GUI)
    # ─────────────────────────────────────────────

    def run(self, procedure, run_mode, image, drawable, config, data):
        if run_mode != Gimp.RunMode.INTERACTIVE:
            return procedure.new_return_values(
                Gimp.PDBStatusType.CALLING_ERROR,
                GLib.Error(
                    "This procedure only supports interactive (GUI) invocation. "
                    f"Use the {BATCH_PROC_NAME} procedure for non-interactive/"
                    "automated runs."
                ),
            )

        GimpUi.init(GUI_PROC_NAME)

        try:
            run_dialog(image, CONFIG)
        except PluginError as exc:
            Gimp.message(str(exc))
            return procedure.new_return_values(
                Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error(str(exc))
            )
        except Exception as exc:
            return _unexpected_error_return(procedure, exc)

        return procedure.new_return_values(
            Gimp.PDBStatusType.SUCCESS, GLib.Error()
        )

    # ─────────────────────────────────────────────
    # RUN (BATCH / CLI)
    # ─────────────────────────────────────────────

    def run_batch(self, procedure, config, data):
        try:
            output_path = self._run_batch(config)
        except PluginError as exc:
            return procedure.new_return_values(
                Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error(str(exc))
            )
        except Exception as exc:
            return _unexpected_error_return(procedure, exc)

        Gimp.message(f"Exportiert nach:\n{output_path}")
        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, None)

    @staticmethod
    def _run_batch(config) -> Path:
        template = config.get_property("template")
        title_text = config.get_property("title")
        title_json = config.get_property("title-json")
        theme = config.get_property("theme")
        name = config.get_property("name")
        date = config.get_property("date")
        output_override = config.get_property("output")

        for label, value in (("template", template), ("theme", theme), ("name", name), ("date", date)):
            if not value:
                raise PluginError(f"Missing required argument: {label}")

        template_path = Path(template)
        if not template_path.is_file():
            raise PluginError(f"Template file does not exist:\n{template_path}")

        richtext = title.parse_title_json(title_json) if title_json else title.simple_richtext(title_text)
        request = ThumbnailRequest(title=richtext, name=name, theme=theme, date=date)

        template_file = Gio.File.new_for_path(str(template_path))
        image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, template_file)
        try:
            service.generate_thumbnail(image, request, CONFIG)

            if output_override:
                output_path = StreamThumbnailHelper._resolve_output_override(
                    output_override, date=date, richtext=richtext
                )
            else:
                output_path = export.build_output_path(config=CONFIG, template_path=template_path, date=date, title=richtext)

            return export.export_png(image, output_path)
        finally:
            image.delete()

    @staticmethod
    def _resolve_output_override(output_override: str, date: str, richtext) -> Path:
        export.parse_date(date)
        candidate = Path(output_override)
        if output_override.endswith(("\\", "/")) or candidate.is_dir():
            title_part = export.title_to_filename_part(richtext)
            return candidate / f"{date}_{title_part}.png"
        return candidate


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

try:
    Gimp.main(StreamThumbnailHelper.__gtype__, sys.argv)
except Exception as e:
    import traceback

    Gimp.message("Plugin crashed:\n" + str(e) + "\n" + traceback.format_exc())
