"""Layer discovery, matching and fallback selection.

No GIMP import here on purpose: real ``Gimp.GroupLayer``/``Gimp.TextLayer``
objects already satisfy the duck-typed checks below (``get_children``,
``get_text``/``set_text``), so this module is importable and unit-testable
without a running GIMP instance.
"""

from __future__ import annotations

import logging

from .models import PluginError

logger = logging.getLogger(__name__)


def _is_group(layer) -> bool:
    return hasattr(layer, "get_children")


def _is_text_layer(layer) -> bool:
    return hasattr(layer, "get_text") and hasattr(layer, "set_text")


def _normalize(value: str) -> str:
    return value.strip().casefold()


def get_all_layers(layers) -> list:
    result = []
    for layer in layers:
        result.append(layer)
        if _is_group(layer):
            result.extend(get_all_layers(layer.get_children()))
    return result


def find_layer_by_name(image, name: str):
    for layer in get_all_layers(image.get_layers()):
        if layer.get_name() == name:
            return layer
    logger.warning("Layer not found: %s", name)
    return None


def find_text_layer_by_name(image, name: str):
    for layer in get_all_layers(image.get_layers()):
        if _is_text_layer(layer) and layer.get_name() == name:
            return layer
    logger.warning("Text layer not found: %s", name)
    return None


def discover_by_prefix(image, prefix: str) -> list[str]:
    """Names of layers starting with `prefix`, with the prefix stripped.

    Preserves layer traversal order; does not sort or deduplicate, matching
    the existing combo-box population behavior.
    """
    names = []
    for layer in get_all_layers(image.get_layers()):
        layer_name = layer.get_name()
        if layer_name.startswith(prefix):
            names.append(layer_name[len(prefix):])
    return names


def reset_visibility(image, prefix: str, default_name: str) -> None:
    """Hides every layer selectable under `prefix`, including its fallback.

    Must be called for a role (image/series) before showing the selected
    layer for that role, so a previously-visible fallback layer can't be
    left showing alongside a newly-selected named layer.
    """
    for layer in get_all_layers(image.get_layers()):
        layer_name = layer.get_name()
        if layer_name.startswith(prefix) or layer_name == default_name:
            layer.set_visible(False)


def select_with_fallback(image, prefix: str, requested: str, fallback_name: str):
    """Finds the layer `prefix + requested` (case-insensitive, trimmed).

    Falls back to `fallback_name` (looked up by exact name) if no match is
    found. Raises PluginError if the fallback layer itself doesn't exist —
    never returns None.

    Returns (layer, used_fallback).
    """
    normalized_requested = _normalize(requested)
    for layer in get_all_layers(image.get_layers()):
        layer_name = layer.get_name()
        if layer_name.startswith(prefix) and _normalize(layer_name[len(prefix):]) == normalized_requested:
            return layer, False

    fallback_layer = find_layer_by_name(image, fallback_name)
    if fallback_layer is None:
        raise PluginError(f"Fallback layer '{fallback_name}' could not be found.")
    return fallback_layer, True
