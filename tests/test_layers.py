import unittest

from core import layers
from core.models import PluginError
from tests.fakes import FakeGroupLayer, FakeImage, FakeLayer, FakeTextLayer


class GetAllLayersTests(unittest.TestCase):
    def test_flattens_nested_groups(self):
        inner = FakeLayer("inner")
        group = FakeGroupLayer("group", [inner])
        top = FakeLayer("top")

        result = layers.get_all_layers([top, group])

        self.assertEqual(result, [top, group, inner])


class FindLayerByNameTests(unittest.TestCase):
    def test_finds_layer_in_nested_group(self):
        target = FakeLayer("@TitleBox")
        image = FakeImage([FakeGroupLayer("group", [target])])

        self.assertIs(layers.find_layer_by_name(image, "@TitleBox"), target)

    def test_returns_none_when_missing(self):
        image = FakeImage([FakeLayer("other")])

        self.assertIsNone(layers.find_layer_by_name(image, "@TitleBox"))


class FindTextLayerByNameTests(unittest.TestCase):
    def test_ignores_non_text_layer_with_same_name(self):
        plain = FakeLayer("@TitleText")
        image = FakeImage([plain])

        self.assertIsNone(layers.find_text_layer_by_name(image, "@TitleText"))

    def test_finds_text_layer(self):
        text_layer = FakeTextLayer("@TitleText")
        image = FakeImage([text_layer])

        self.assertIs(layers.find_text_layer_by_name(image, "@TitleText"), text_layer)


class DiscoverByPrefixTests(unittest.TestCase):
    def test_strips_prefix_and_preserves_order(self):
        image = FakeImage([
            FakeLayer("@Image John"),
            FakeLayer("@Background Autumn"),
            FakeLayer("@Image Jane"),
        ])

        self.assertEqual(layers.discover_by_prefix(image, "@Image "), ["John", "Jane"])

    def test_returns_empty_list_when_no_match(self):
        image = FakeImage([FakeLayer("@Background Autumn")])

        self.assertEqual(layers.discover_by_prefix(image, "@Image "), [])


class ResetVisibilityTests(unittest.TestCase):
    def test_hides_prefixed_and_default_layers_only(self):
        john = FakeLayer("@Image John", visible=True)
        default = FakeLayer("@DefaultImage", visible=True)
        unrelated = FakeLayer("@TitleText", visible=True)
        image = FakeImage([john, default, unrelated])

        layers.reset_visibility(image, "@Image ", "@DefaultImage")

        self.assertFalse(john.visible)
        self.assertFalse(default.visible)
        self.assertTrue(unrelated.visible)


class SelectWithFallbackTests(unittest.TestCase):
    def test_exact_match(self):
        john = FakeLayer("@Image John")
        default = FakeLayer("@DefaultImage")
        image = FakeImage([john, default])

        layer, used_fallback = layers.select_with_fallback(image, "@Image ", "John", "@DefaultImage")

        self.assertIs(layer, john)
        self.assertFalse(used_fallback)

    def test_match_is_case_insensitive_and_trimmed(self):
        john = FakeLayer("@Image John")
        default = FakeLayer("@DefaultImage")
        image = FakeImage([john, default])

        layer, used_fallback = layers.select_with_fallback(image, "@Image ", "  john ", "@DefaultImage")

        self.assertIs(layer, john)
        self.assertFalse(used_fallback)

    def test_missing_requested_uses_fallback(self):
        default = FakeLayer("@DefaultImage")
        image = FakeImage([default])

        layer, used_fallback = layers.select_with_fallback(image, "@Image ", "Ghost", "@DefaultImage")

        self.assertIs(layer, default)
        self.assertTrue(used_fallback)

    def test_missing_fallback_raises_plugin_error(self):
        image = FakeImage([])

        with self.assertRaises(PluginError):
            layers.select_with_fallback(image, "@Image ", "Ghost", "@DefaultImage")


if __name__ == "__main__":
    unittest.main()
