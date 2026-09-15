import unittest

from core.config import PluginConfig
from core.models import PluginError, ThumbnailRequest
from core.service import GimpRuntime, generate_thumbnail
from core.title import simple_richtext
from tests.fakes import FakeImage, FakeLayer, FakeTextLayer


def make_runtime() -> GimpRuntime:
    return GimpRuntime(
        pixel_unit="px",
        channel_replace="REPLACE",
        fill_foreground="FILL_FOREGROUND",
        black_color="black",
        set_foreground=lambda color: None,
        clear_selection=lambda image: None,
        flush_displays=lambda: None,
    )


def make_image(config: PluginConfig) -> FakeImage:
    title_layer = FakeTextLayer(config.title_layer_name, text="Old Title")
    title_layer.width, title_layer.height = 400, 100

    box_layer = FakeLayer(config.title_box_layer_name)
    box_layer.offsets = (100, 100)
    box_layer.width, box_layer.height = 500, 150

    label_layer = FakeTextLayer(config.label_layer_name)

    return FakeImage([
        title_layer,
        box_layer,
        label_layer,
        FakeLayer(config.image_prefix + "John"),
        FakeLayer(config.image_prefix + "Jane"),
        FakeLayer(config.default_image_layer_name),
        FakeLayer(config.series_prefix + "Autumn"),
        FakeLayer(config.default_series_layer_name),
    ])


def find(image, name):
    for layer in image.get_layers():
        if layer.get_name() == name:
            return layer
    raise AssertionError(f"layer {name} not found in fake image")


class GenerateThumbnailTests(unittest.TestCase):
    def setUp(self):
        self.config = PluginConfig()
        self.image = make_image(self.config)
        self.runtime = make_runtime()

    def _request(self, title_text="New Title", name="John", theme="Autumn"):
        return ThumbnailRequest(title=simple_richtext(title_text), name=name, theme=theme, date="2026-09-15")

    def test_happy_path_updates_title_label_and_visibility(self):
        result = generate_thumbnail(self.image, self._request(), self.config, self.runtime)

        title_layer = find(self.image, self.config.title_layer_name)
        label_layer = find(self.image, self.config.label_layer_name)
        self.assertEqual(title_layer.get_text(), "New Title")
        self.assertEqual(label_layer.get_text(), "John")

        john = find(self.image, self.config.image_prefix + "John")
        jane = find(self.image, self.config.image_prefix + "Jane")
        default_image = find(self.image, self.config.default_image_layer_name)
        autumn = find(self.image, self.config.series_prefix + "Autumn")
        default_series = find(self.image, self.config.default_series_layer_name)

        self.assertTrue(john.visible)
        self.assertFalse(jane.visible)
        self.assertFalse(default_image.visible)
        self.assertTrue(autumn.visible)
        self.assertFalse(default_series.visible)

        self.assertFalse(result.used_name_fallback)
        self.assertFalse(result.used_theme_fallback)
        self.assertIsNone(result.output_path)

    def test_empty_title_leaves_existing_text_untouched(self):
        generate_thumbnail(self.image, self._request(title_text=""), self.config, self.runtime)

        title_layer = find(self.image, self.config.title_layer_name)
        self.assertEqual(title_layer.get_text(), "Old Title")

    def test_unknown_name_falls_back_and_is_reported(self):
        result = generate_thumbnail(self.image, self._request(name="Ghost"), self.config, self.runtime)

        default_image = find(self.image, self.config.default_image_layer_name)
        john = find(self.image, self.config.image_prefix + "John")
        self.assertTrue(default_image.visible)
        self.assertFalse(john.visible)
        self.assertTrue(result.used_name_fallback)
        # The label text still shows the requested (if unmatched) name verbatim.
        label_layer = find(self.image, self.config.label_layer_name)
        self.assertEqual(label_layer.get_text(), "Ghost")

    def test_missing_required_layer_raises_plugin_error(self):
        image = FakeImage([FakeLayer("irrelevant")])

        with self.assertRaises(PluginError):
            generate_thumbnail(image, self._request(), self.config, self.runtime)

    def test_missing_fallback_layer_raises_plugin_error(self):
        image = make_image(self.config)
        image._layers = [layer for layer in image._layers if layer.get_name() != self.config.default_image_layer_name]

        with self.assertRaises(PluginError):
            generate_thumbnail(image, self._request(name="Ghost"), self.config, self.runtime)

    def test_box_layer_is_cleared_and_refilled(self):
        generate_thumbnail(self.image, self._request(), self.config, self.runtime)

        box_layer = find(self.image, self.config.title_box_layer_name)
        self.assertTrue(box_layer.cleared)
        self.assertEqual(box_layer.filled_with, self.runtime.fill_foreground)
        self.assertEqual(len(self.image.selections), 2)


if __name__ == "__main__":
    unittest.main()
