"""Minimal fake layer/image objects for core/ unit tests.

These deliberately implement only the method names the real Gimp.Layer /
Gimp.TextLayer / Gimp.GroupLayer / Gimp.Image objects expose that core/
actually calls — core/layers.py and core/service.py duck-type against these
names rather than importing gi, so a real Gimp object satisfies the exact
same shape.
"""

from __future__ import annotations


class FakeLayer:
    def __init__(self, name: str, visible: bool = True):
        self._name = name
        self.visible = visible
        self.offsets = (0, 0)
        self.width = 0
        self.height = 0
        self.cleared = False
        self.filled_with = None
        self.image = None

    def get_name(self) -> str:
        return self._name

    def get_image(self):
        return self.image

    def set_visible(self, value: bool) -> None:
        self.visible = value

    def get_visible(self) -> bool:
        return self.visible

    def get_offsets(self):
        return (True, self.offsets[0], self.offsets[1])

    def set_offsets(self, x: int, y: int) -> None:
        self.offsets = (x, y)

    def get_width(self) -> int:
        return self.width

    def get_height(self) -> int:
        return self.height

    def edit_clear(self) -> None:
        self.cleared = True

    def edit_fill(self, fill_type) -> None:
        self.filled_with = fill_type


class FakeTextLayer(FakeLayer):
    def __init__(self, name: str, text: str = "", visible: bool = True):
        super().__init__(name, visible)
        self._text = text
        self.font_size = None
        self.font_size_unit = None
        self.markup = None

    def get_text(self) -> str:
        return self._text

    def set_text(self, text: str) -> None:
        self._text = text
        self.markup = None

    def set_markup(self, markup: str) -> None:
        self.markup = markup

    def set_font_size(self, size: float, unit) -> None:
        self.font_size = size
        self.font_size_unit = unit

    def get_font(self):
        return "SomeFont"


class FakeGroupLayer(FakeLayer):
    def __init__(self, name: str, children: list, visible: bool = True):
        super().__init__(name, visible)
        self._children = children

    def get_children(self) -> list:
        return self._children


class FakeImage:
    def __init__(self, layers: list, resolution: tuple = (True, 72.0, 72.0)):
        self._layers = layers
        self.selections: list[tuple] = []
        self.resolution = resolution
        for layer in layers:
            layer.image = self

    def get_layers(self) -> list:
        return self._layers

    def select_rectangle(self, channel_op, x, y, w, h) -> None:
        self.selections.append((channel_op, x, y, w, h))

    def get_resolution(self):
        return self.resolution
