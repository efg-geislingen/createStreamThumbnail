import unittest
from pathlib import Path

from core import export
from core.config import PluginConfig
from core.models import PluginError
from core.title import simple_richtext


class ParseDateTests(unittest.TestCase):
    def test_accepts_valid_iso_date(self):
        self.assertEqual(export.parse_date("2026-09-15"), "2026-09-15")

    def test_rejects_malformed_date(self):
        with self.assertRaises(PluginError):
            export.parse_date("15-09-2026")

    def test_rejects_invalid_calendar_date(self):
        with self.assertRaises(PluginError):
            export.parse_date("2026-13-40")


class TitleToFilenamePartTests(unittest.TestCase):
    def test_joins_runs_and_replaces_newlines_with_space(self):
        richtext = simple_richtext("Woodworking\nCourse")

        self.assertEqual(export.title_to_filename_part(richtext), "Woodworking Course")

    def test_sanitizes_filesystem_invalid_characters(self):
        richtext = simple_richtext('A/B:C*D?E"F<G>H|I')

        self.assertEqual(export.title_to_filename_part(richtext), "A_B_C_D_E_F_G_H_I")

    def test_trims_trailing_dots_and_spaces(self):
        richtext = simple_richtext("Title.  ")

        self.assertEqual(export.title_to_filename_part(richtext), "Title")


class BuildOutputPathTests(unittest.TestCase):
    def test_builds_path_under_output_subdir(self):
        config = PluginConfig()
        template_path = Path("C:/Thumbnails/livestream_template.xcf")
        richtext = simple_richtext("Woodworking Course")

        result = export.build_output_path(config, template_path, "2026-09-15", richtext)

        self.assertEqual(
            result,
            Path("C:/Thumbnails/output/2026-09-15_Woodworking Course.png"),
        )

    def test_rejects_invalid_date(self):
        config = PluginConfig()
        template_path = Path("C:/Thumbnails/livestream_template.xcf")
        richtext = simple_richtext("Title")

        with self.assertRaises(PluginError):
            export.build_output_path(config, template_path, "not-a-date", richtext)


if __name__ == "__main__":
    unittest.main()
