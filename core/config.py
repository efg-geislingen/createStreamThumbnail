from dataclasses import dataclass


@dataclass(frozen=True)
class PluginConfig:
    # Layer names inside the template.
    title_layer_name: str = "@TitleText"
    title_box_layer_name: str = "@TitleBox"
    label_layer_name: str = "@LabelText"
    default_image_layer_name: str = "@DefaultImage"
    default_series_layer_name: str = "@DefaultBackground"

    # Prefixes used to discover selectable layers.
    image_prefix: str = "@Image "
    series_prefix: str = "@Background "

    # Title centering/box layout (pixels).
    title_anchor: tuple[int, int] = (683, 239)
    box_padding: tuple[int, int, int] = (5, 20, 50)  # top, bottom, side

    # Default font sizes (pixels), used when a text run doesn't specify one.
    default_title_size: float = 120.0
    default_name_size: float = 80.0

    # Export.
    output_subdir: str = "output"
