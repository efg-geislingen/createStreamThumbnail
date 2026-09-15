# Refactoring Plan — Stream Thumbnail Helper

This plan is written against the actual current implementation in
[`createStreamThumbnail.py`](../../createStreamThumbnail.py), not against the
hypothetical structure sketched in [`SPEC.md`](../SPEC.md). Where the two
disagree, this document says so explicitly and explains what will actually be
preserved.

---

## 1. Phase 1 — Reconnaissance findings

### Current entry point
Single file, `createStreamThumbnail.py`. `StreamThumbnailHelper(Gimp.PlugIn)`
registers one procedure, `"python-fu-stream-thumbnail-helper"`, via
`do_query_procedures` / `do_create_procedure` (lines 181–221). Menu path
`<Image>/EFG Plugins`. It is a `Gimp.ImageProcedure`, so GIMP always supplies
an already-open `image` + `drawable` — there is no template-loading step and
no `run_mode` check, so the dialog always shows, even in batch/non-interactive
invocation.

### Current GIMP API
GIMP 3 (`gi.require_version("Gimp", "3.0")`), `GimpUi` 3.0, `Gegl` 0.4. Uses
`Gimp.ImageProcedure.new`, `proc.add_image_argument` / `add_drawable_argument`
with raw `GObject.ParamFlags.READWRITE`, `Gimp.TextLayer` / `Gimp.GroupLayer`
isinstance checks, `Gimp.context_set_foreground(Gegl.Color.new(...))`,
`image.select_rectangle` + `edit_clear` / `edit_fill` for box redraw. These are
all valid GIMP 3 patterns (not leftover GIMP 2 API) — no GIMP-2-isms found
that need correcting.

### Current GUI
A hand-built `Gtk.Dialog` (`show_dialog`, lines 93–174), not
`GimpUi.ProcedureDialog`. Three fields: a single-line `Gtk.Entry` for the
title, and two `Gtk.ComboBoxText` widgets for "Prediger" (preacher/name) and
"Predigt-Reihe" (series/theme). `title_size` (120.0) and `label_size` (80.0)
are hardcoded Python floats, not exposed in the UI at all.

### "Theme" mechanism (SPEC calls it Theme; code calls it **Series/Background**)
There is **no group/folder**. `show_dialog` walks *every* layer in the image
(`get_all_layers`, flattening groups) and collects the suffix of any layer
name starting with `SERIES_PREFIX = "@Background "` (line 101–102). The combo
box is populated from these names directly from actual layer names — this
already satisfies SPEC §9's "dynamically discovered, no hardcoded list"
requirement, just via prefix-matching rather than a group.

### "Name" mechanism (SPEC calls it Name; code calls it **Preacher/Image**)
Same pattern, `IMAGE_PREFIX = "@Image "` (lines 98–99).

**Discrepancy to flag:** SPEC.md §9–§10 describe Theme/Name as being
discovered from children of dedicated `Themes`/`Names` *groups*. The real
template does not use groups — discovery is prefix-based over the flat layer
list. Per SPEC §2/§41 ("preserve existing behavior unless a demonstrable bug"
/ "avoid rewriting working behavior for stylistic reasons"), **the refactor
will keep prefix-based discovery**, just extract it into one reusable
function instead of two copy-pasted loops. It will not introduce groups.

### Fallback mechanism
`find_layer_by_name` does an exact-name lookup. If the prefixed layer for the
selected name/series isn't found, the code falls back to
`DEFAULT_IMAGE_LAYER_NAME = "@DefaultImage"` / `DEFAULT_SERIES_LAYER_NAME =
"@DefaultBackground"` (lines 314–321). Matches SPEC §13's intent already.

### Title mechanism
`TITLE_LAYER_NAME = "@TitleText"` is looked up as a `Gimp.TextLayer` and its
text is replaced wholesale via `set_text()` (line 268). Font is "changed" via
`title_layer.set_font(title_layer.get_font())` — a no-op self-reassignment,
almost certainly dead leftover code. Size is forced to the hardcoded 120px.
Positioning: after setting the text, the layer is centered on a fixed pixel
anchor `cx, cy = 683, 239` (line 279), and a background box layer
(`@TitleBox`) is cleared and redrawn to fit the new text bounds plus padding
(`pT, pB, pS = 5, 20, 50`). This center-and-box logic must be preserved
pixel-for-pixel.

### Export mechanism
**There isn't one.** The plugin only mutates the already-open GIMP image and
calls `Gimp.displays_flush()`. No PNG (or any format) is ever written. Today,
exporting is a manual step the user performs in GIMP after running the
plugin. This is the single biggest gap versus SPEC.md, which assumes export
is already part of the flow — it has to be built from scratch, for both the
new CLI path and a new explicit GUI action (decided below, §4a).

### Registration
One PDB procedure, no `run_mode` branching, no string/JSON arguments beyond
image/drawable. To support batch invocation this needs a second procedure
(see §5).

### Potential bugs found (see §3 for the fix list)
Concrete, numbered list in §3.

---

## 2. Guiding constraint

This is a 342-line script, not a large system. Per SPEC §6/§41, the source
layout below is deliberately smaller than SPEC's suggested tree — no
`gimp/api.py`, no `selectors/` package, no `title/parser.py` as a separate
module from the model, etc. Modules are only split out where it buys real
testability or reuse (GUI vs. CLI sharing logic), not for its own sake.

---

## 3. Bugs / risks discovered (fix during refactor, not silently)

1. **Stray default layer stays visible.** The visibility-reset loop (lines
   307–309) only hides layers whose name starts with `IMAGE_PREFIX` or
   `SERIES_PREFIX`. `@DefaultImage` / `@DefaultBackground` don't match either
   prefix, so they are never explicitly hidden — if a previous run left a
   default layer visible and this run resolves to a *named* layer instead,
   both can end up visible simultaneously. Fix: the reset loop must also
   cover the two default layer names, and visibility of exactly one
   image-role layer and one series-role layer must be asserted, not assumed.
2. **Missing fallback layer crashes instead of erroring clearly.** If
   `DEFAULT_IMAGE_LAYER_NAME`/`DEFAULT_SERIES_LAYER_NAME` themselves don't
   exist, `find_layer_by_name` returns `None` (after a `Gimp.message`) and the
   subsequent `.set_visible(True)` throws an unhandled `AttributeError`.
   SPEC §13 explicitly requires a clear raised error here instead.
3. **Dead/no-op font reassignment.** `title_layer.set_font(title_layer.get_font())`
   and the equivalent for `label_layer` (lines 266, 270) do nothing useful —
   remove, or replace with an actual intended font if one was meant.
4. **Title entry pre-fill is broken and disabled.** Line 126 is commented out
   with `# TODO this breaks for some reason`. Needs a real fix (reading
   `Gimp.TextLayer.get_text()` correctly) as part of GUI rework, not
   silently left broken.
5. **Combo boxes always reset to index 0** instead of reflecting the layer
   that's currently visible in the image (`set_active(0)`, lines 134, 141) —
   matches the TODO "On startup, set values to currently active layers."
6. **Title is single-line only.** `Gtk.Entry` cannot hold `\n` at all — this
   blocks the rich-text/newline requirement structurally, not just
   cosmetically.
7. **`title_size` / `label_size` are hardcoded** (120.0 / 80.0), never read
   from the current layer or exposed to the user, despite a TODO implying
   they should be.
8. **No `run_mode` handling.** The procedure always shows the modal dialog,
   which will hang/fail under `-i` (non-interactive) batch invocation. Needed
   for any CLI story.
9. **No try/finally around the selection-based box redraw.** If
   `edit_clear`/`edit_fill`/offset lookups fail partway, the image can be
   left with an active selection and partially-cleared box layer. Should be
   wrapped so `Gimp.Selection.none(image)` always runs.
10. **Broad catch only at top level** (line 338, `except Exception`) — this
    is acceptable as a last-resort crash reporter (not a *bare* `except`,
    and it surfaces the traceback via `Gimp.message`), so it stays, but no
    additional bare excepts should be introduced elsewhere.

None of these are behavior the user relies on (they're bugs, not features),
so fixing them does not violate "preserve existing behavior."

---

## 4. Target architecture (scaled down from SPEC §5/§6)

```
createStreamThumbnail.py     # GIMP entry point: registration only (both procedures)
core/
    __init__.py
    config.py                # PluginConfig dataclass: prefixes, layer names, anchor, padding
    models.py                 # ThumbnailRequest, ThumbnailResult, TextRun, RichText
    layers.py                 # get_all_layers, find_layer_by_name, find_text_layer_by_name,
                               # discover_by_prefix(), select_with_fallback() — pure-ish,
                               # takes the image as a duck-typed root, testable with fakes
    title.py                  # RichText -> Pango markup renderer, \r\n normalization,
                               # simple-string and JSON title parsing
    service.py                # generate_thumbnail(image, request, config) — the one
                               # shared orchestration used by both GUI and batch procedure
    export.py                 # export_png(image, output_path)
gui/
    __init__.py
    dialog.py                 # Gtk.Dialog, builds a ThumbnailRequest, calls core.service
tests/
    test_layers.py
    test_title.py
    test_service.py
README.md
```

No `gimp/api.py` abstraction layer, no `selectors/` package, no `cli.py` — see
§5 for why a standalone CLI script is not the right shape here. `core/layers.py`
and `core/title.py` are written to be importable and unit-testable without a
running GIMP: the discovery/fallback/title-parsing algorithms take plain
name/children structures (real `Gimp.GroupLayer`/`Gimp.TextLayer` objects
already satisfy that shape via duck typing — `get_name()`, `get_children()` —
so no separate fake-vs-real adapter class is needed, just fakes with the same
two methods in tests).

### 4a. GUI: Preview vs. Export (decided)

The dialog gains a **date field** (`Gtk.Entry`, format `YYYY-MM-DD`,
pre-filled with today's date, validated by the same shared date-parsing
function the CLI uses) and **two action buttons** instead of a single OK:

- **Preview** — runs `core.service.generate_thumbnail(image, request,
  config)` only: selects Theme/Name layers, renders the title, redraws the
  title box. Flushes the display so the user sees the result in the open
  GIMP image. No file is written. This is exactly today's behavior.
- **Export** — runs the same `generate_thumbnail` call, then additionally
  calls `core.export.export_png(image, output_path)` (§4b) using the current
  dialog field values (it does not depend on Preview having been clicked
  first — each button independently builds the request from the current
  fields and calls the same shared step, so there is no duplicated apply
  logic and no hidden state between clicks).

Both buttons keep the dialog **open** afterward (only a separate
Cancel/Close button, or the window close box, dismisses it), so the user can
adjust title/theme/name/date and click Preview or Export again. This is a
control-flow change from today's single blocking `dialog.run()` → close:
button `clicked` signals are connected individually instead of relying on
one `Gtk.ResponseType`, and errors (e.g. missing layer, bad date, export
failure) are surfaced via `Gimp.message` without closing the dialog.

### 4b. Fixed output folder and filename (decided)

Output goes to a **dedicated subfolder next to the template file** — e.g.
template `C:\Thumbnails\livestream_template.xcf` exports into
`C:\Thumbnails\output\`. The subfolder name (`"output"`) is a
`PluginConfig.output_subdir` default, created on first export if missing
(`Path.mkdir(parents=True, exist_ok=True)`, per SPEC §30).

Filename: **`YYYY-MM-DD_Title.png`**, e.g. `2026-09-15_Woodworking Course.png`,
built by `core/export.py`:

```python
def build_output_path(config: PluginConfig, template_path: Path, date: str, title: RichText) -> Path
```

- `date` is validated as `YYYY-MM-DD` (`datetime.date.fromisoformat`) by one
  shared `core` function used by both GUI (on Preview/Export click) and CLI
  (on `--date` parsing) — invalid dates are rejected with a clear error
  ("Invalid date '2026-13-40', expected YYYY-MM-DD"), never silently
  coerced.
- `Title` is derived from the `RichText` by joining all run texts in order
  (ignoring font/size/style — only the plain text matters for the filename),
  with `\n` replaced by a single space, then sanitizing characters that are
  invalid in Windows filenames (`\ / : * ? " < > |` → `_`) and trimming
  trailing whitespace/dots. Multiple runs like `"Woodworking\n"` + `"Course"`
  become `Woodworking Course` in the filename.
- If a file already exists at the computed path (e.g. Export clicked twice
  the same day with the same title), it is **overwritten** — matches SPEC
  §29's "running the same command twice produces the same result" rather
  than accumulating `_1`, `_2` suffixes.

---

## 5. CLI design (SPEC §19–§22)

A standalone `cli.py` that imports `gi`/`Gimp` directly, as SPEC §19 warns,
would either require Python running inside GIMP's own interpreter anyway (in
which case it's not really "standalone") or would silently pretend to be a
plugin without being one. Instead:

1. Add a **second PDB procedure**, `"python-fu-stream-thumbnail-batch"`,
   registered as a plain `Gimp.Procedure` (not `Gimp.ImageProcedure` — it has
   no open image to receive). Arguments: `template` (string path), `title`
   (string), `title-json` (optional string, path or inline JSON), `theme`
   (string), `name` (string), `date` (string, `YYYY-MM-DD`), `output`
   (optional string — see below). It always runs non-interactively:
   `Gimp.file_load(template)` → build `ThumbnailRequest` →
   `core.service.generate_thumbnail(...)` → `core.export.export_png(...)` →
   `image.delete()` (never touches/overwrites `template`, satisfying SPEC
   §29's idempotency requirement).
2. `--date` mirrors the GUI's new date field exactly (same
   `YYYY-MM-DD` validation, same shared function — see §4b) and, together
   with `--title`/`--title-json`, feeds `core.export.build_output_path` to
   produce `<template's folder>/output/YYYY-MM-DD_Title.png` by default.
   `--output` is **optional**: if given, it overrides the destination (a
   full file path, or a directory to place the auto-named file into)
   instead of the default `output/` subfolder next to the template — this
   keeps SPEC §20's explicit `--output PATH` available for automation setups
   that need a specific destination, without breaking the default
   date+title-based naming just established for the GUI.
3. Invocation goes through GIMP's own batch interface, e.g.:
   ```
   gimp-console -i -b '(python-fu-stream-thumbnail-batch RUN-NONINTERACTIVE
       "template.xcf" "Woodworking\nCourse" "" "Autumn" "John" "2026-09-15" "")' \
       -b '(gimp-quit 0)'
   ```
4. A thin wrapper shell/batch script (or a short Python `argparse` front-end
   that just shells out to `gimp-console` with the right `-b` string, quoting
   carefully) can be provided purely for ergonomics — e.g. so a user can type
   `python thumbnail_cli.py --template t.xcf --title "..." --theme Autumn
   --name John --date 2026-09-15` — but its only job is argument
   parsing/validation and building that batch command line; **it must not
   reimplement any selection/title/export logic**. This satisfies "the CLI
   layer must ultimately invoke the same application service" because the
   real work happens inside the `python-fu-stream-thumbnail-batch` procedure,
   which calls `core.service.generate_thumbnail` — the exact same function
   the GUI dialog calls.
5. Exit status: the wrapper propagates `gimp-console`'s exit code; the batch
   procedure returns `Gimp.PDBStatusType.EXECUTION_ERROR` with a `GLib.Error`
   message on any validation/layer/export failure so the failure is visible
   both in GIMP's own error reporting and via the wrapper's exit code.
6. Rich text input: `--title` accepts a plain string (with literal `\n`,
   normalized from `\r\n`); `--title-json` accepts the structured
   `{"runs": [...]}` form from SPEC §21, either as a path to a file or an
   inline JSON string, parsed by `core/title.py`.

---

## 6. Rich text rendering strategy (SPEC §14–§18, §37–§38)

**To verify in Phase 1 of implementation** (quick check against the installed
GIMP 3 PDB before writing renderer code): `Gimp.TextLayer.set_markup()` /
PDB procedure `gimp-text-layer-set-markup`, which accepts Pango markup
(`<span font="..." size="..." style="italic" weight="bold">...</span>`).
This has existed since GIMP 2.10's text tool rework and should carry into
GIMP 3's PDB. If confirmed present, this is **Option A** from SPEC §16 and is
strongly preferred: one real, still-editable `Gimp.TextLayer`, multiple fonts
and sizes and styles in a single layer, and native `\n` handling — no
rasterization, no multi-layer positioning hacks.

Renderer (`core/title.py`):
- `RichText`/`TextRun` dataclasses as in SPEC §15.
- Simple string input (`--title "Woodworking\nCourse"` or the existing GUI
  entry) becomes a single `TextRun` with no explicit font/size — rendered as
  plain text via `set_text()` exactly as today (byte-for-byte backward
  compatible path, so existing single-font titles are untouched).
- Structured/multi-run input renders via `set_markup()`, escaping each run's
  text for XML/Pango (`&`, `<`, `>`), emitting a `<span>` per run with only
  the attributes that were actually specified (so an unset font/size falls
  back to the layer's current default rather than forcing one).
- `\r\n` → `\n` normalization happens once, at parse time, for both simple
  and structured input.
- **Fallback plan if `set_markup` turns out unavailable/unreliable on the
  target GIMP version**: fall back to SPEC §16 Option B (one text layer per
  run, positioned in sequence inside a group under the existing title
  anchor). This is a straightforward swap inside `core/title.py`'s renderer
  only — `core/service.py` and everything upstream stays the same either way
  because they just call `title_renderer.render(image, richtext, target)`.
- Centering logic (SPEC §17): unchanged algorithm (`cx, cy` anchor +
  `get_width()`/`get_height()` of the resulting layer, box redraw with the
  same padding constants), now pulled from `PluginConfig` instead of being
  inline magic numbers.

---

## 7. Data model (SPEC §7, adapted to actual layer roles)

```python
@dataclass
class TextRun:
    text: str
    font: str | None = None
    size: float | None = None
    bold: bool | None = None
    italic: bool | None = None

@dataclass
class RichText:
    runs: list[TextRun]

@dataclass
class ThumbnailRequest:
    title: RichText
    name: str      # SPEC's "Name" == current "Prediger"/@Image selection
    theme: str     # SPEC's "Theme" == current "Predigt-Reihe"/@Background selection
    date: str      # YYYY-MM-DD, used for the export filename (§4b)

@dataclass
class ThumbnailResult:
    output_path: Path | None   # None for a Preview-only run; set after Export
    selected_name: str
    selected_theme: str
    used_name_fallback: bool
    used_theme_fallback: bool
```

`core/config.py` holds the current hardcoded constants as a `PluginConfig`
dataclass (`title_layer_name`, `title_box_layer_name`, `label_layer_name`,
`default_image_layer_name`, `default_series_layer_name`, `image_prefix`,
`series_prefix`, `title_anchor=(683, 239)`, `box_padding=(5, 20, 50)`,
`default_title_size=120.0`, `default_name_size=80.0`, `output_subdir="output"`)
— same values as today, just named and centralized instead of scattered
module-level constants, per SPEC §32.

### Name/Theme matching (decided)

Matching becomes **case-insensitive and whitespace-trimmed** (both leading
and trailing), implemented once in `core/layers.py` and used identically by
GUI and CLI/batch — satisfying SPEC §11's "if normalization is part of the
intended behavior, make it deliberate and documented." This is safe for the
GUI because combo box values are always exact, unmodified layer-name
suffixes, so trimming/casing never changes what they match; it only matters
for free-typed CLI/batch input, and the user confirmed layer names are
always clearly distinguishable even case-insensitively.

---

## 8. Implementation phases

**Status: Phases 1-5 and 7 done.** (Phase 6 tests were written
incrementally alongside each phase rather than as one batch at the end —
49 tests total in `tests/`.) Phase 7: wrote `README.md` covering GUI usage,
CLI/batch invocation (both `cli.py` and the raw `gimp-console`/Script-Fu
command, including the `--batch-interpreter` requirement discovered during
Phase 4 testing), rich-text JSON format, the actual `@Image `/`@Background `
prefix-based template structure (not SPEC's hypothetical Themes/Names
groups), fallback behavior, and the known limitations surfaced during
manual testing (PNG metadata warnings, unaddressed bug #7). All phases in
the original plan are now complete.

**Phase 5 robustness audit findings:** walked through SPEC §28's checklist
(exceptions, GIMP object lifecycle, layer visibility, missing groups/
fallback/title layers, invalid paths, export failures, repeated execution).
Most were already correct from earlier phases (image lifecycle via
duplicate+`finally: delete()` in `core/export.py` and `_run_batch`;
visibility reset covers defaults; fallback/missing-layer errors are already
explicit `PluginError`s; repeated runs overwrite deterministically since
each batch invocation loads a fresh image and computes the same output
path from date+title). One real gap found and fixed: an unexpected
non-`PluginError` exception (e.g. a permissions error creating the output
folder, a corrupt template) had nowhere to land —
- In `createStreamThumbnail.py`, both `run()` and `run_batch()` only caught
  `PluginError`; anything else would escape the PDB run callback
  uncontrolled. Added a shared `_unexpected_error_return(procedure, exc)`
  helper (logs via `Gimp.message` + traceback, returns `EXECUTION_ERROR`)
  and a generic `except Exception` in both, after the specific
  `PluginError` catch.
- In `gui/dialog.py`, the same gap would have crashed the *entire modal
  dialog* over one bad click (worse than the CLI case, since Preview/Export
  errors are meant to keep the dialog open for another attempt). Added the
  same specific-then-generic catch pattern inside the per-click try block.
- Wrapped the whole `dialog.run()` loop in `try/finally: dialog.destroy()`
  so the GTK dialog is always cleaned up, even if something escapes both
  `except` clauses.

49 tests still passing; re-verified all touched files import cleanly under
GIMP's real bindings. **Not yet re-tested live in GIMP** — these are
error-path changes (the happy path is unchanged), so a full retest isn't
strictly necessary, but it's worth at least reopening the GUI once to
confirm the nested try/finally in `gui/dialog.py` didn't change normal
Preview/Export/Cancel behavior.

`core/config.py`, `core/models.py`,
`core/layers.py`, `core/title.py` (simple-string path), `core/service.py`
(+ `GimpRuntime` seam so it's testable without `gi`) are in place, with 34
passing `unittest` tests under `tests/` (`python -m unittest discover -s
tests`, no extra dependencies).

`core/export.py` (§4b's `build_output_path`/`parse_date`/`export_png`) was
pulled forward from Phase 4 into Phase 2, since the GUI's new Export button
needs it to actually work rather than being a stub — verified against GIMP
3.2.2's real Python bindings via introspection (`Gimp.file_save(run_mode,
image, file, options=None) -> bool`, `Gimp.Image.duplicate()`/`.flatten()`,
`Gimp.TextLayer.get_text()`, `Gimp.Image.get_file()`, `GimpUi.init(name)`,
`Gimp.PDBStatusType.CALLING_ERROR`). Phase 4 now only needs to add the batch
PDB procedure + CLI wrapper on top of the already-built `core/export.py`.

`createStreamThumbnail.py` is rewired: `gui/dialog.py` now builds a
`ThumbnailRequest` and calls `core.service.generate_thumbnail`, with the
two-button Preview/Export flow, a date field, multiline title input with
prefill, and Name/Theme combos pre-selected to the currently-visible layer.
`run()` now rejects non-`INTERACTIVE` run modes with `CALLING_ERROR` instead
of hanging. All new/changed files import cleanly under GIMP's own bundled
Python (`C:\Program Files\GIMP 3\bin\python.exe`) with the real `Gimp`/
`GimpUi`/`Gtk` bindings — **not yet manually exercised inside a running GIMP
session**, so the manual test matrix (§36) still needs to be run by hand.

Known gap carried over, not yet fixed: bug #7 (title/label font sizes are
still fixed `PluginConfig` defaults, not read from the current layer or
exposed in the UI) — deferred as a minor UX item, not a functional
regression, since sizes still match today's hardcoded values.

**Status: Phase 3 done.** `core/title.py` now implements the full rich-text
story: `parse_title_json` (inline JSON or a file path, per SPEC §21, with
clear `PluginError`s for malformed/missing-`runs`/missing-`text` input) and
multi-run rendering via `Gimp.TextLayer.set_markup()` — confirmed present on
GIMP 3.2.2 by introspecting the real bindings. A title still renders via
plain `set_text()`/`set_font_size()` (byte-identical to today) whenever it's
a single run with no font/bold/italic override, even if it sets an explicit
`size` — markup is only used when per-character formatting is actually
needed (2+ runs, or any font/bold/italic). A run that leaves an attribute
unset emits no `<span>` for it, so it inherits the layer's base font.

Verified empirically against GIMP's real Pango bindings
(`Pango.parse_markup`), not assumed: the markup `size` attribute must be a
plain integer in 1024ths of a point — `"64px"` is rejected outright — so an
explicit per-run pixel size is converted using the layer's image resolution
(`image.get_resolution()`, falling back to 72 DPI if that call fails) before
being placed in markup. This conversion path is exercised by unit tests at
the default 72 DPI; **not yet manually verified inside GIMP** at a
non-72-DPI template resolution, so please check a run with an explicit
`size` renders at the visually correct pixel size in your real template.

The GUI's multiline title field is unaffected — `simple_richtext()` still
produces a single unstyled run, so it keeps using the exact `set_text()`
path as before. The structured-JSON path is CLI/batch-only, per §24, and
will be wired up in Phase 4.

29 new/changed rich-text tests added (`tests/test_title.py`, `tests/fakes.py`
extended with `get_image()`/`get_resolution()`/`set_markup()`) — 43 tests
total, all passing, still gi-free.

**Status: Phase 4 done, not yet manually tested.** Added a second PDB
procedure, `python-fu-stream-thumbnail-batch` (a plain `Gimp.Procedure`, not
`Gimp.ImageProcedure` — confirmed via introspection that its `run_func`
signature is `(procedure, config: Gimp.ProcedureConfig, run_data)`, with no
`run_mode` argument at all, unlike the GUI procedure). It loads the
template via `Gimp.file_load`, builds a `ThumbnailRequest` (from `--title`
or `--title-json`, via `core/title.py`'s existing parser), calls the exact
same `core.service.generate_thumbnail`, resolves the output path via
`core.export.build_output_path` (or an explicit `--output` override — a
directory or full file path), exports via `core.export.export_png`, and
always calls `image.delete()` in a `finally` so the loaded template is
never left open. `cli.py` is a thin `argparse` wrapper with no `gi`
dependency of its own — it only builds the Script-Fu batch command string
(`(python-fu-stream-thumbnail-batch "template" "title" "title-json" "theme"
"name" "date" "output")`) and shells out to `gimp-console-3.2.exe -i -b
"<call>" -b "(gimp-quit 0)"` via `subprocess.run` with an argv list (no
shell involved, so no shell-quoting/injection concerns).

Note versus the original §5 sketch: there is no `RUN-NONINTERACTIVE`
argument in the actual call — confirmed via introspection that plain
`Gimp.Procedure`s don't take a run-mode argument at all (only
`Gimp.ImageProcedure` does); the procedure is unconditionally
non-interactive by construction, so the Script-Fu call is just
`(python-fu-stream-thumbnail-batch "template" ...)`.

5 new pure-Python tests for `cli.py`'s argument parsing and Scheme-string
escaping (`tests/test_cli.py`) — 48 tests total, all passing.

**Manually tested by the user in GIMP 3.2.2 — works end-to-end, both
paths.** Called directly from the Script-Fu console
(`(python-fu-stream-thumbnail-batch "template.xcf" "Test Title" "" "Autumn"
"John" "2026-09-15" "")` → `(#t)`, thumbnail created correctly), and via
`cli.py` → `gimp-console-3.2.exe` (same successful result, plus the German
"Exportiert nach: ...output\2026-09-15_Test Title.png" message, confirming
the same code path as the GUI's Export button).

Two things surfaced and fixed during this test:
- `gimp-console` in GIMP 3 requires `--batch-interpreter=plug-in-script-fu-eval`
  explicitly (no longer defaults to Script-Fu like GIMP 2.10 did) — added
  to `cli.py`'s command line.
- Calling the batch procedure with positional/ordered-list arguments logs a
  Script-Fu deprecation warning ("Calling Plug-In PDB procedures with
  arguments as an ordered list is deprecated"). Switched `cli.py` to
  named-argument syntax (`#:template "..." #:title "..." ...`), matching
  the replacement GIMP's own warning suggested. 49 tests now (one new test
  locks in the named-argument format).

Same benign "PNG-Bild-Warnung: Operation not supported" ×5 as the GUI
Export path (§ above) — confirms it's a general limitation of this GIMP
build for any PNG export, not something specific to either code path.

Also cleaned up: GIMP logged "The catalog directory does not exist:
...\locale" / "Override method set_i18n() ..." / "Localization disabled"
on every batch invocation (we ship no translations, so there's no
`locale/` folder). Overrode `Gimp.PlugIn.do_set_i18n` to return
`(False, None, None)`, which GIMP's own message suggested — confirmed gone
on re-test. The one remaining console line,
`GLib-GIRepository-CRITICAL: ... Typelib file for namespace 'GLibWin32'
... not found`, is a pre-existing quirk of this GIMP Windows build's
GObject-Introspection setup — it appears on *every* invocation of GIMP's
bundled Python, including plain introspection completely unrelated to this
plugin, so it's environmental, not something in our code to fix.

**Manually tested by the user in GIMP 3.2.2**: GUI dialog, Preview, and
Export all work correctly end-to-end against the real template; exported
PNG is correct. One cosmetic finding: `Gimp.file_save` logs five
"Operation not supported" warnings to the Error Console on every Export
(one per PNG metadata category — EXIF/IPTC/XMP/thumbnail/comment — minus
color profile). Tried clearing `export_image`'s metadata before saving;
made no difference, so reverted that change. This is treated as a benign
limitation of this GIMP Windows build (most likely missing `exiv2`/
metadata-writer support) rather than a plugin bug — the exported file
itself is confirmed correct — and is not pursued further.

1. **Core extraction** (no behavior change): pull `get_all_layers`,
   `find_layer_by_name`, `find_text_layer_by_name`, and a new
   `discover_by_prefix(image, prefix)` / `select_with_fallback(...)` into
   `core/layers.py`. Pull the title/box positioning math into
   `core/service.py` calling into `core/title.py`'s simple-string path only
   (rich text comes in phase 3). Fix bugs #1, #2, #3, #9 from §3 here, since
   they're pure logic fixes with no GUI/CLI-shape implications.
2. **GUI adapter**: rewrite `show_dialog`/`run()` to build a
   `ThumbnailRequest` and call `core.service.generate_thumbnail`. Fix bugs
   #4, #5, #6 (multiline `Gtk.TextView` instead of `Gtk.Entry`), #7
   (expose size fields or read current layer size as default), #8 (branch on
   `run_mode`). Add the date field and switch to the two-button
   Preview/Export flow from §4a (this replaces the single blocking
   `dialog.run()` with individually connected button-`clicked` handlers).
3. **Rich text**: implement `core/title.py` per §6, wire the GUI's multiline
   text field to the simple-string path (still one font, but newlines now
   work end-to-end), and add the structured-JSON path used only by the batch
   procedure/CLI for now (no need to build a multi-font GUI editor — SPEC
   §24 explicitly allows exposing structured rich text only via CLI while the
   GUI keeps a simple editor).
4. **Batch procedure + CLI wrapper** (`core/export.py` already built in
   Phase 2 and wired into the GUI's Export button): implement
   `python-fu-stream-thumbnail-batch` and the CLI wrapper per §5, reusing
   `core/export.py` so the folder/filename logic keeps exactly one
   implementation shared by GUI and CLI.
5. **Robustness audit**: re-check resource cleanup (image.delete() on every
   exit path of the batch procedure, including failures — use try/finally),
   confirm original template file is never written to, confirm repeated CLI
   runs against the same template/date/title produce identical output
   (same overwritten file, per §4b).
6. **Tests**: `tests/test_layers.py` (discovery + fallback, using tiny fake
   layer objects with `.get_name()`/`.get_children()`), `tests/test_title.py`
   (simple string, `\r\n` normalization, JSON parsing valid/invalid, markup
   escaping), `tests/test_service.py` (mocked layer manager, verifies the
   select→render→(export) call sequence). None require a running GIMP.
7. **Documentation**: `README.md` covering GUI usage, batch/CLI invocation
   syntax (with the actual `gimp-console -b ...` command verified to work
   against the installed GIMP), rich-text JSON format, template layer/prefix
   conventions (`@Image `, `@Background `, `@TitleText`, `@TitleBox`,
   `@LabelText`, `@DefaultImage`, `@DefaultBackground`), and fallback
   behavior.

---

## 9. Decisions confirmed with the user

- **GUI export**: two buttons, Preview (no export, today's behavior) and
  Export (apply + export); dialog stays open across clicks. See §4a.
- **Filename**: `YYYY-MM-DD_Title.png`, date from a new GUI field / CLI
  `--date`, written to an `output/` subfolder next to the template by
  default (CLI can override via optional `--output`). See §4b.
- **Matching**: case-insensitive, whitespace-trimmed for Name/Theme, one
  shared implementation. See §7.
- **GIMP version for testing**: 3.2.2, installed locally — Phase 1 of
  implementation will verify `gimp-text-layer-set-markup` against this
  build before committing to the Option A renderer in §6.
- **Packaging**: stays a drop-in folder inside GIMP's plug-ins directory, as
  today (no build/install step required for the plugin to run — sibling
  `core`/`gui` imports resolve via the entry script's own directory being on
  `sys.path`). Since the user is open to more, an **optional** convenience
  script (e.g. `tools/install.ps1`) that symlinks this repo into GIMP's real
  `%APPDATA%\GIMP\3.0\plug-ins\` folder can be added for dev convenience —
  optional, not required, and not part of the plugin's runtime behavior.

## 10. GIMP binary location (confirmed)

`C:\Program Files\GIMP 3\bin\gimp-console-3.2.exe` — confirmed present via
directory listing. The batch invocation in §5 and the README's CLI example
will use this exact path (the console variant, not `gimp-3.2.exe`, so CLI
runs don't spawn a GUI process).
