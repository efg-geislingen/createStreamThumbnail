import json
import unittest

from core import title
from core.models import PluginError, RichText, TextRun
from tests.fakes import FakeImage, FakeTextLayer


class NormalizeNewlinesTests(unittest.TestCase):
    def test_converts_windows_newlines(self):
        self.assertEqual(title.normalize_newlines("a\r\nb"), "a\nb")

    def test_converts_lone_carriage_return(self):
        self.assertEqual(title.normalize_newlines("a\rb"), "a\nb")

    def test_leaves_unix_newlines_untouched(self):
        self.assertEqual(title.normalize_newlines("a\nb"), "a\nb")


class SimpleRichtextTests(unittest.TestCase):
    def test_produces_single_unstyled_run(self):
        richtext = title.simple_richtext("Woodworking\r\nCourse")

        self.assertEqual(len(richtext.runs), 1)
        run = richtext.runs[0]
        self.assertEqual(run.text, "Woodworking\nCourse")
        self.assertIsNone(run.font)
        self.assertIsNone(run.size)


class RenderTests(unittest.TestCase):
    def _layer(self):
        layer = FakeTextLayer("@TitleText")
        FakeImage([layer])  # links layer.image, resolution defaults to 72 DPI
        return layer

    def test_plain_run_uses_set_text_not_markup(self):
        layer = self._layer()
        richtext = title.simple_richtext("Hello")

        title.render(layer, richtext, default_size=120.0, unit="px")

        self.assertEqual(layer.get_text(), "Hello")
        self.assertIsNone(layer.markup)
        self.assertEqual(layer.font_size, 120.0)
        self.assertEqual(layer.font_size_unit, "px")

    def test_plain_run_size_overrides_default(self):
        layer = self._layer()
        richtext = RichText(runs=[TextRun(text="Hello", size=64.0)])

        title.render(layer, richtext, default_size=120.0, unit="px")

        self.assertEqual(layer.font_size, 64.0)

    def test_multiple_runs_render_as_markup(self):
        layer = self._layer()
        richtext = RichText(runs=[
            TextRun(text="Woodworking\n", font="Font A", size=72.0),
            TextRun(text="Course", font="Font B", size=64.0),
        ])

        title.render(layer, richtext, default_size=120.0, unit="px")

        self.assertIn('font_family="Font A"', layer.markup)
        self.assertIn('font_family="Font B"', layer.markup)
        self.assertIn("Woodworking\n", layer.markup)
        self.assertIn("Course", layer.markup)
        # base layer size is set once for runs that don't specify their own
        self.assertEqual(layer.font_size, 120.0)

    def test_unstyled_run_in_multi_run_title_has_no_span(self):
        layer = self._layer()
        richtext = RichText(runs=[TextRun(text="Plain "), TextRun(text="Bold", bold=True)])

        title.render(layer, richtext, default_size=120.0, unit="px")

        self.assertTrue(layer.markup.startswith("Plain "))
        self.assertIn('font_weight="bold"', layer.markup)

    def test_size_attribute_is_pango_units_at_72dpi(self):
        layer = self._layer()
        richtext = RichText(runs=[TextRun(text="A", size=72.0), TextRun(text="B", bold=True)])

        title.render(layer, richtext, default_size=120.0, unit="px")

        # At 72 DPI, 72px == 72pt == 72 * 1024 Pango units.
        self.assertIn('size="73728"', layer.markup)

    def test_markup_escapes_special_characters(self):
        layer = self._layer()
        richtext = RichText(runs=[TextRun(text="A & B < C", bold=True)])

        title.render(layer, richtext, default_size=120.0, unit="px")

        self.assertIn("A &amp; B &lt; C", layer.markup)


class ParseTitleJsonTests(unittest.TestCase):
    def test_parses_inline_json(self):
        raw = json.dumps({"runs": [
            {"text": "Woodworking\n", "font": "Font A", "size": 72},
            {"text": "Course", "font": "Font B", "size": 64},
        ]})

        richtext = title.parse_title_json(raw)

        self.assertEqual(len(richtext.runs), 2)
        self.assertEqual(richtext.runs[0].text, "Woodworking\n")
        self.assertEqual(richtext.runs[0].font, "Font A")
        self.assertEqual(richtext.runs[1].size, 64)

    def test_normalizes_windows_newlines_in_runs(self):
        raw = json.dumps({"runs": [{"text": "A\r\nB"}]})

        richtext = title.parse_title_json(raw)

        self.assertEqual(richtext.runs[0].text, "A\nB")

    def test_rejects_invalid_json_syntax(self):
        with self.assertRaises(PluginError):
            title.parse_title_json("{not valid json")

    def test_rejects_missing_runs_key(self):
        with self.assertRaises(PluginError):
            title.parse_title_json(json.dumps({"title": "no runs here"}))

    def test_rejects_empty_runs_array(self):
        with self.assertRaises(PluginError):
            title.parse_title_json(json.dumps({"runs": []}))

    def test_rejects_run_without_text(self):
        with self.assertRaises(PluginError):
            title.parse_title_json(json.dumps({"runs": [{"font": "Font A"}]}))

    def test_missing_file_path_raises_clear_error(self):
        with self.assertRaises(PluginError):
            title.parse_title_json("C:/does/not/exist.json")


if __name__ == "__main__":
    unittest.main()
