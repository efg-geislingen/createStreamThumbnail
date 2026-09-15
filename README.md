# Stream Thumbnail Helper

A GIMP 3 plugin that fills in a livestream/sermon thumbnail template
(title, preacher, series background) from a GTK dialog or from the command
line, and exports the result as a PNG — without ever modifying the
template file itself.

## Installation

GIMP loads Python plugins from a folder that must have the **same name as
the entry script**. Place (or link) this whole folder as:

```
%APPDATA%\GIMP\3.0\plug-ins\createStreamThumbnail\
```

so that `createStreamThumbnail.py` sits directly inside a folder named
`createStreamThumbnail`, alongside `core/`, `gui/`, `cli.py`. Restart GIMP
afterward — Python plugins are only discovered on startup.

## GUI usage

1. Open your template `.xcf` file in GIMP (it must be a saved file on disk
   — Export needs to know where to put the output relative to it).
2. Run **Image → EFG Plugins → "Stream-Thumbnail aktualisieren..."**.
3. Fill in:
   - **Predigt-Titel** — multi-line title text. Leave it blank to keep
     whatever title is already in the template unchanged (the box/centering
     still gets recalculated either way).
   - **Prediger** / **Predigt-Reihe** — pick from the dropdowns, which are
     populated dynamically from the template's layers (see
     [Template structure](#template-structure)). Both default to whichever
     layer is currently visible.
   - **Datum** — `YYYY-MM-DD`, defaults to today; used to build the export
     filename.
4. **Preview** applies the title/name/theme changes to the open image so
   you can see them on canvas — it does not write any file. Click it as
   many times as you like while you adjust fields.
5. **Export** does the same, plus writes a PNG to
   `<template's folder>\output\YYYY-MM-DD_Title.png` (see
   [Fallback behavior](#fallback-behavior) and
   [Known limitations](#known-limitations)). A message shows the exact
   path once it's done.
6. **Cancel** (or closing the dialog) just closes it — it does not undo
   anything a Preview/Export click already applied to the open image.

The template file on disk is never written to by either button. Export
works on a duplicated, flattened copy of the image; your open image keeps
all its layers exactly as before.

## CLI / batch usage

For unattended/automated runs, without opening GIMP's UI at all. Two ways
to trigger it — both end up calling the exact same underlying logic as the
GUI:

### `cli.py` (recommended)

```
python cli.py --template "C:\Templates\template.xcf" --title "Predigttitel" --theme Richter --name "Max Mustermann" --date 2026-09-15
```

Arguments:

| Flag | Required | Meaning |
| --- | --- | --- |
| `--template` | yes | Path to the `.xcf` template |
| `--title` | no | Plain title text (use an actual newline or `\n` for line breaks) |
| `--title-json` | no | Structured rich-text title — inline JSON or a path to a `.json` file; overrides `--title`. See [Rich text titles](#rich-text-titles) |
| `--theme` | yes | Requested Predigt-Reihe |
| `--name` | yes | Requested Prediger |
| `--date` | yes | `YYYY-MM-DD`, used for the export filename |
| `--output` | no | Overrides the default `output/` subfolder — give it a directory (the usual filename is still generated inside it) or a full file path |
| `--gimp-console` | no | Path to `gimp-console(.exe)`, default `C:\Program Files\GIMP 3\bin\gimp-console-3.2.exe` |
| `--verbose` | no | Print the underlying GIMP batch command before running it |

Exit status mirrors `gimp-console`'s exit code.

### Calling the PDB procedure directly

`cli.py` only builds and runs this command — useful to know for
troubleshooting, or from Script-Fu/another tool:

```
"C:\Program Files\GIMP 3\bin\gimp-console-3.2.exe" -i --batch-interpreter=plug-in-script-fu-eval -b "(python-fu-stream-thumbnail-batch #:template \"C:\\Templates\\template.xcf\" #:title \"Predigttitel\" #:title-json \"\" #:theme \"Richter\" #:name \"Max Mustermann\" #:date \"2026-09-15\" #:output \"\")" -b "(gimp-quit 0)"
```

(GIMP 3's `gimp-console` requires `--batch-interpreter=plug-in-script-fu-eval`
explicitly — it no longer defaults to Script-Fu the way GIMP 2.10 did.)

You can also call it interactively from GIMP's own
**Filters → Script-Fu → Console** while testing — same syntax, without the
`gimp-console`/`-b`/`-i` wrapper.

## Rich text titles

**Simple** (GUI text field, or `--title`): one font, with real line breaks.
Renders via GIMP's plain `set_text`, so existing single-font titles are
completely unaffected.

**Structured** (`--title-json` only — the GUI keeps its simple editor, per
design): multiple runs, each with its own optional font/size/bold/italic.
Either an inline JSON string or a path to a `.json` file:

```json
{
  "runs": [
    { "text": "Predigt\n", "font": "Font A", "size": 72 },
    { "text": "Titel", "font": "Font B", "size": 64, "bold": true }
  ]
}
```

- `text` is required; `font`, `size` (pixels), `bold`, `italic` are all
  optional — a run that omits one inherits the title layer's current
  value for it.
- Rendered as Pango markup on the existing `@TitleText` layer (via
  `Gimp.TextLayer.set_markup`) whenever there's more than one run or any
  styling — it stays a real, editable GIMP text layer, never rasterized.
- If you need per-character formatting from inside GIMP itself instead,
  just edit the title with GIMP's own text tool afterward — the plugin
  only rewrites the title when you give it non-empty text.

## Template structure

The plugin looks for these layers anywhere in the image (nested inside
groups is fine):

| Layer name | Purpose |
| --- | --- |
| `@TitleText` | The title text layer |
| `@TitleBox` | Background box behind the title — cleared and redrawn to fit whatever the title currently measures |
| `@LabelText` | The Prediger/name text layer |
| `@Image <Name>` | One per selectable Prediger, e.g. `@Image Max Mustermann`, `@Image Maja Musterfrau` |
| `@Background <Theme>` | One per selectable Predigt-Reihe, e.g. `@Background Richter` |
| `@DefaultImage` | Shown when the requested name doesn't match any `@Image <Name>` layer |
| `@DefaultBackground` | Shown when the requested theme doesn't match any `@Background <Theme>` layer |

Adding a new `@Image <Name>` or `@Background <Theme>` layer makes it
available immediately — no code changes, no restart needed (just reopen
the plugin dialog, or pass the new name to the CLI).

## Fallback behavior

Matching a requested Name/Theme against `@Image <Name>` / `@Background
<Theme>` layers is **case-insensitive and trims leading/trailing
whitespace**. If nothing matches, the corresponding `@Default...` layer is
shown instead, and the result reports that a fallback was used. If even
the fallback layer is missing from the template, the plugin raises a clear
error (`Fallback layer '@DefaultImage' could not be found.`) rather than
silently doing nothing.

## Known limitations

- GIMP logs five `PNG-Bild-Warnung: Operation not supported` lines on
  every export (EXIF/IPTC/XMP/thumbnail/comment metadata categories this
  GIMP Windows build can't write, most likely missing `exiv2`). Harmless —
  the exported PNG itself is correct.
- Title/label font sizes are fixed defaults (120px/120px title box target,
  80px name), same as before this refactor — not yet read from the
  layer's current size or exposed as an editable field.
- "Deactivate buttons until all inputs have values" and "per-line title
  box sizing" are pre-existing TODOs, not yet implemented.

## Development

```
core/            data models, layer discovery/fallback, title parsing+rendering,
                 export, and the shared application service (GUI and CLI both
                 call core.service.generate_thumbnail)
gui/dialog.py    the GTK dialog — no selection/export logic of its own
cli.py           thin argparse wrapper that shells out to gimp-console
createStreamThumbnail.py   GIMP plugin registration (both procedures) + entry point
tests/           unit tests, no GIMP required to run them
AGENT/plans/refactoring.md   the refactor plan and a running log of what changed
```

Run the tests:

```
python -m unittest discover -s tests
```

No extra dependencies — `core/layers.py` and the parsing parts of
`core/title.py`/`core/export.py` are plain Python with no `gi` import at
all; the few functions that genuinely need a live GIMP API (rendering,
export, the actual PDB calls) import `gi` lazily and are exercised through
fakes in `tests/fakes.py` instead.
