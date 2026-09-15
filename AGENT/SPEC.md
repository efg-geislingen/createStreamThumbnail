# GIMP 3 Thumbnail Plugin

## Refactoring, CLI Support & Rich Text Specification

---

# 1. Objective

Refactor the existing GIMP 3 plugin.

The current plugin was built quickly and without extensive knowledge of the GIMP API. It currently works through a graphical interface but should now become a robust, maintainable, extensible plugin that can also be invoked from the command line.

The refactoring has four primary goals:

1. **Preserve the existing GUI workflow.**
2. **Add a CLI/non-interactive interface.**
3. **Support rich text for the thumbnail Title**, including:
   - multiple fonts within one title
   - multiple font sizes/styles where technically appropriate
   - line breaks/new lines

4. **Refactor the codebase** to:
   - eliminate obvious bugs and inconsistencies
   - improve error handling
   - improve GIMP API usage
   - separate concerns
   - make the code scalable for future features

The existing plugin's current behavior should be treated as the functional baseline unless explicitly changed by this specification.

---

# 2. Important Principle

Do not blindly rewrite the plugin.

First understand the existing implementation.

Before modifying code:

1. Inspect every plugin source file.
2. Identify all GIMP API calls.
3. Identify how the GUI is created.
4. Identify how Theme layers are discovered.
5. Identify how Name layers are discovered.
6. Identify how fallback layers are selected.
7. Identify how the Title is currently inserted.
8. Identify how the XCF/template is opened.
9. Identify how the final image is exported.
10. Identify how the plugin is registered with GIMP.
11. Identify the GIMP 3 version/API conventions being used.

Document the existing architecture and behavior before changing it.

---

# 3. Preserve Existing Functionality

The existing GUI must continue to work after the refactoring.

The following behavior must remain:

```text
GUI
 │
 ├── Title input
 ├── Theme selection
 └── Name selection
       │
       ▼
   Template
       │
       ├── Theme layer selected
       ├── Name layer selected
       └── Title inserted
       │
       ▼
    Result
```

The existing Theme and Name lists are generated from the layers contained under their respective folders/groups.

If a new layer is added to the Theme folder, it should automatically become available as a Theme option.

If a new layer is added to the Name folder, it should automatically become available as a Name option.

Do not replace this dynamic behavior with hard-coded lists.

---

# 4. Existing Fallback Behavior

The existing plugin has fallback layers.

If a selected Theme does not exist:

```text
requested Theme
      ↓
no matching layer
      ↓
Theme fallback layer
```

Likewise:

```text
requested Name
      ↓
no matching layer
      ↓
Name fallback layer
```

Preserve this behavior.

The CLI must use exactly the same underlying selection logic as the GUI.

There must NOT be separate implementations such as:

```text
GUI Theme selection → implementation A
CLI Theme selection → implementation B
```

Instead:

```text
             ┌─────────────────────┐
             │ Shared Core Logic   │
             └──────────┬──────────┘
                        │
              ┌─────────┴─────────┐
              ▼                   ▼
          GUI adapter         CLI adapter
```

---

# 5. Target Architecture

Refactor toward the following conceptual architecture:

```text
                    ┌─────────────────────┐
                    │    GIMP Plugin     │
                    └──────────┬──────────┘
                               │
                 ┌─────────────┴─────────────┐
                 │                           │
                 ▼                           ▼
        ┌─────────────────┐        ┌─────────────────┐
        │ GUI Interface   │        │ CLI Interface   │
        └────────┬────────┘        └────────┬────────┘
                 │                          │
                 └────────────┬─────────────┘
                              ▼
                    ┌──────────────────┐
                    │ Application Core │
                    └────────┬─────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
     Template           Layer Manager      Title Renderer
     Manager
          │                  │                  │
          └──────────────────┼──────────────────┘
                             ▼
                       GIMP API Layer
```

The exact implementation may differ after inspecting the existing code, but the principle should remain:

**UI code must not contain the core image manipulation logic.**

---

# 6. Suggested Source Structure

Refactor toward something similar to:

```text
plugin/
│
├── README.md
├── requirements.txt              # only if actually required
│
├── plugin_entry.py               # GIMP registration/entry point
│
├── cli.py                        # CLI argument handling
│
├── application/
│   ├── __init__.py
│   ├── service.py                # high-level thumbnail operation
│   └── models.py                 # input/output data models
│
├── gimp/
│   ├── __init__.py
│   ├── api.py                    # GIMP API abstraction
│   ├── layers.py                 # layer/group operations
│   ├── template.py               # template operations
│   ├── text.py                   # GIMP text operations
│   └── export.py                 # image export
│
├── title/
│   ├── __init__.py
│   ├── model.py                  # rich-text data model
│   ├── parser.py                 # CLI/input parsing
│   └── renderer.py               # title → GIMP text representation
│
├── selectors/
│   ├── __init__.py
│   └── layers.py                 # Theme/Name selection + fallback
│
├── gui/
│   ├── __init__.py
│   └── dialog.py
│
├── config/
│   ├── __init__.py
│   └── defaults.py
│
└── tests/
    ├── test_selectors.py
    ├── test_title_parser.py
    ├── test_models.py
    └── test_application.py
```

Do not mechanically create every file above if the existing plugin is small.

Use the architecture where it provides real separation of concerns.

Avoid over-engineering.

---

# 7. Core Data Model

Introduce a single input model for thumbnail generation.

Conceptually:

```python
@dataclass
class ThumbnailRequest:
    title: Title
    theme: str
    name: str
```

The result should contain useful information such as:

```python
@dataclass
class ThumbnailResult:
    output_path: Path | None
    selected_theme: str
    selected_name: str
    used_theme_fallback: bool
    used_name_fallback: bool
```

The exact model can be adapted to the existing implementation.

The important requirement is that the GUI and CLI both eventually produce the same `ThumbnailRequest`.

---

# 8. Application Service

Create a high-level service responsible for generating a thumbnail.

Conceptually:

```python
result = thumbnail_service.generate(
    request,
    template_path=...,
    output_path=...,
)
```

This service should orchestrate:

1. Validate input.
2. Load/open template.
3. Discover Theme and Name layers.
4. Select Theme.
5. Select Name.
6. Apply Title.
7. Export image.
8. Return result.

It should NOT contain GUI-specific code.

It should NOT parse CLI arguments.

It should NOT directly manipulate GTK widgets.

---

# 9. Theme Layer Discovery

Implement a robust layer/group discovery mechanism.

The plugin should identify the configured Theme group/folder.

Within that group:

```text
Themes
├── Autumn
├── Winter
├── Spring
├── Summer
└── Default
```

The available themes should be determined dynamically from the actual GIMP layer/group structure.

Do not hard-code:

```python
themes = ["Autumn", "Winter", "Spring", "Summer"]
```

The same mechanism should be used by both GUI and CLI.

---

# 10. Name Layer Discovery

Likewise:

```text
Names
├── John
├── Jane
├── Bob
└── Default
```

The available names must be dynamically determined from the GIMP template.

Adding a new layer should require no Python code changes.

---

# 11. Layer Matching

Define one consistent matching strategy.

For example:

```text
requested value
       ↓
exact layer-name match
       ↓
matching layer found → select/show it
       ↓
no match → fallback
```

Do not silently perform unpredictable case transformations unless the existing plugin already does so.

If case-insensitive matching is desirable, make it deliberate and documented.

Handle whitespace consistently.

For example:

```text
" Autumn "
```

should not unexpectedly behave differently from:

```text
"Autumn"
```

if normalization is part of the intended behavior.

---

# 12. Layer Visibility

Review the current implementation for visibility bugs.

Ensure that selecting a Theme/Name reliably produces:

```text
selected layer = visible
other mutually exclusive layers = hidden
```

Do not assume a layer is hidden merely because another layer is visible.

Explicitly set visibility where appropriate.

Check nested groups carefully.

The implementation must not accidentally hide unrelated template layers.

---

# 13. Fallback Layers

Make fallback selection explicit.

Avoid fragile logic such as:

```python
layers[-1]
```

or:

```python
layers[0]
```

unless the template structure guarantees this.

Prefer an explicit fallback layer name/configuration.

For example:

```python
THEME_FALLBACK_NAME = "Default"
NAME_FALLBACK_NAME = "Default"
```

However, if the current plugin already has an established fallback mechanism, preserve it unless there is a demonstrable bug.

If the fallback layer cannot be found, raise a clear error:

```text
Theme fallback layer 'Default' could not be found.
```

Do not silently do nothing.

---

# 14. Rich Text Requirement

The Title must now support rich text.

The current title system presumably treats the Title as a simple string.

Replace this assumption with a structured title representation.

The title must support:

- multiple fonts
- multiple text styles where GIMP supports them
- multiple font sizes where appropriate
- line breaks/new lines

Example conceptual title:

```text
Woodworking
Course
```

where:

```text
Woodworking → Font A
Course      → Font B
```

The implementation must support arbitrary numbers of text runs.

---

# 15. Rich Text Data Model

Use a structured representation.

Conceptually:

```python
@dataclass
class TextRun:
    text: str
    font: str | None = None
    size: float | None = None
    bold: bool | None = None
    italic: bool | None = None
```

And:

```python
@dataclass
class RichText:
    runs: list[TextRun]
```

Do not limit the model to exactly two fonts.

For example, this should be representable:

```text
Run 1 → "Woodworking" → Font A
Run 2 → " Course"     → Font B
Run 3 → " 2026"       → Font C
```

Line breaks must be representable inside text runs.

For example:

```python
TextRun(
    text="Woodworking\nCourse",
    font="Some Font"
)
```

---

# 16. Rich Text Rendering Strategy

Before implementing the renderer, inspect what GIMP 3's text API actually supports.

Do not assume that a GIMP text layer supports arbitrary per-character font assignment through the same API as a simple text layer.

Determine whether the correct implementation is:

### Option A — One GIMP text layer with rich text attributes

Preferred if the GIMP 3 API provides a robust supported mechanism.

OR

### Option B — Multiple GIMP text layers

If the GIMP API cannot reliably create the required rich-text formatting in a single text layer, use multiple text layers, one per text run.

For example:

```text
Title Group
├── Text Run 1
├── Text Run 2
└── Text Run 3
```

The plugin can position the individual text layers to visually form one title.

However, do not implement this until the existing template's structure and desired visual behavior are understood.

---

# 17. Preserve Existing Title Positioning

The current template presumably has a designated title position/area.

The refactoring must preserve the current title placement.

Do not change the visual appearance of existing titles unless required.

If the current title uses a particular text layer as its anchor, retain that concept.

Create a dedicated abstraction:

```python
title_renderer.render(
    image,
    title,
    target=title_target
)
```

so future changes to title rendering do not affect Theme/Name handling.

---

# 18. Newline Handling

The title must support explicit newlines.

For example:

```text
Woodworking
Course
```

must result in an actual two-line rendered title.

Do not convert newlines to spaces.

Preserve:

```text
\n
```

during parsing and rendering.

Also ensure Windows-style:

```text
\r\n
```

does not result in malformed text.

Normalize input internally to:

```text
\n
```

---

# 19. CLI Interface

The plugin must support non-interactive execution.

The exact CLI mechanism must be chosen based on how GIMP 3 plugins are registered and invoked.

The target behavior is:

```text
gimp-thumbnail-plugin \
    --template "template.xcf" \
    --title "Woodworking Course" \
    --theme "Autumn" \
    --name "John" \
    --output "thumbnail.png"
```

The actual invocation may instead need to be through GIMP's own console/batch/procedure mechanism.

Do not create a standalone Python program that pretends to be a GIMP plugin if the GIMP API requires execution inside GIMP.

The CLI layer must ultimately invoke the same application service as the GUI.

---

# 20. CLI Parameters

The CLI must support at minimum:

```text
--template PATH
--title TEXT
--theme TEXT
--name TEXT
--output PATH
```

Optional:

```text
--verbose
--dry-run
--help
```

The exact CLI syntax can be adjusted to the actual GIMP 3 plugin invocation mechanism.

---

# 21. CLI Rich Text Input

The CLI must provide a practical way to specify rich text.

Do not invent an overly complicated custom syntax unless necessary.

Prefer a structured input format.

Possible approach:

```text
--title-file title.json
```

where:

```json
{
  "runs": [
    {
      "text": "Woodworking\n",
      "font": "Font A",
      "size": 72
    },
    {
      "text": "Course",
      "font": "Font B",
      "size": 64
    }
  ]
}
```

The CLI should also support a simple title string:

```text
--title "Woodworking\nCourse"
```

When the simple form is used, render the entire title using the default title formatting.

The structured format should be used when multiple fonts/styles are required.

---

# 22. CLI Input Validation

Validate:

```text
template exists
output directory exists or can be created
title is present
theme is present
name is present
rich-text JSON is valid
fonts are valid where validation is possible
```

Return non-zero exit status on failure.

Error messages must be useful to a human or automation script.

Example:

```text
ERROR: Template file does not exist:
C:\Templates\livestream_template.xcf
```

---

# 23. GUI Refactoring

The GUI should become a thin layer.

It should:

1. Discover available Themes.
2. Discover available Names.
3. Collect Title input.
4. Construct a `ThumbnailRequest`.
5. Pass the request to the application service.
6. Display errors/results.

The GUI should not directly contain:

- layer traversal algorithms
- fallback logic
- export implementation
- duplicated title-rendering logic

---

# 24. GUI Rich Text Editing

The GUI must be reviewed in light of the rich-text requirement.

The existing simple Title input should continue to work.

At minimum:

```text
Title:
Woodworking
Course
```

must preserve the newline.

For multiple fonts, determine the most appropriate UI after inspecting the existing plugin and GIMP 3 capabilities.

Possible approaches:

### Approach A

Provide a rich-text editor in the plugin dialog.

### Approach B

Provide a title configuration/import mechanism.

### Approach C

Expose structured rich-text configuration through CLI while retaining the existing simple GUI.

Do not build a complicated rich-text editor merely for the sake of the requirement if GIMP's own text editing facilities can provide the desired functionality.

However, the underlying application service must support rich text independently of the GUI.

---

# 25. Separation of Concerns

The following must remain separate:

```text
CLI argument parsing
        ≠
GUI
        ≠
business/application logic
        ≠
GIMP API calls
        ≠
layer selection
        ≠
text rendering
        ≠
export
```

For example, this is bad:

```python
def button_clicked():
    # find layers
    # hide layers
    # select layers
    # modify text
    # export
```

Prefer:

```python
def button_clicked():
    request = build_request_from_gui()
    service.generate(request)
```

---

# 26. GIMP API Abstraction

Review all direct GIMP API usage.

Where practical, centralize repeated operations such as:

```text
get layer name
get children
find group
set visibility
find text layer
set text
set font
export image
```

Do not create abstractions for every single GIMP function.

The goal is readable code, not an enormous abstraction framework.

---

# 27. Error Handling

Replace silent failures with explicit errors.

Bad:

```python
try:
    ...
except:
    pass
```

Do not use bare `except`.

Catch specific errors where possible.

Errors should contain context.

Bad:

```text
Error
```

Good:

```text
Could not find Theme group 'Themes' in the template.
```

Good:

```text
Could not export PNG to:
C:\output\thumbnail.png
```

---

# 28. Resource Management

Review:

- image loading
- image closing
- drawable/layer references
- temporary layers
- temporary files
- GIMP procedures
- GUI resources

Ensure documents are not accidentally left open after CLI execution.

CLI execution should be suitable for repeated automated runs.

---

# 29. Idempotency

Running the same CLI command twice should produce the same result rather than progressively modifying the same template.

Never modify the original template permanently unless explicitly requested.

Preferred flow:

```text
Original XCF
    ↓
Open copy/in-memory image
    ↓
Apply modifications
    ↓
Export PNG
    ↓
Close without modifying original
```

The original template should remain unchanged.

---

# 30. Export

Create a dedicated export component.

It should:

1. Validate output path.
2. Ensure parent directory exists.
3. Export PNG using the supported GIMP 3 API.
4. Verify that the operation completed successfully.
5. Return the output path.

Avoid hard-coded output paths.

---

# 31. Logging

Add structured logging where practical.

CLI should support:

```text
--verbose
```

Normal:

```text
INFO: Loading template
INFO: Selecting Theme: Autumn
INFO: Selecting Name: John
INFO: Rendering title
INFO: Exporting PNG
INFO: Completed
```

Verbose:

```text
DEBUG: Found Theme group
DEBUG: Available themes: ...
DEBUG: Matched Theme layer: Autumn
DEBUG: Found Name group
DEBUG: Matched Name layer: John
DEBUG: Rendering 2 text runs
```

Do not log sensitive information.

---

# 32. Configuration

Any currently hard-coded names should be identified.

Examples:

```text
Themes
Names
Default
Title
```

Determine which values are genuinely structural and which should be configurable.

Do not move every string into a configuration file unnecessarily.

A reasonable configuration might be:

```python
@dataclass
class PluginConfig:
    themes_group: str = "Themes"
    names_group: str = "Names"
    theme_fallback: str = "Default"
    name_fallback: str = "Default"
    title_layer: str = "Title"
```

Use the existing names discovered in the current plugin.

---

# 33. Backward Compatibility

Existing users must still be able to open GIMP and use the plugin normally.

Existing workflow:

```text
Open GIMP
↓
Run plugin
↓
Dialog
↓
Select Theme
↓
Select Name
↓
Enter Title
↓
Generate thumbnail
```

must remain functional.

CLI is an additional interface, not a replacement.

---

# 34. Tests

Add tests for all logic that does not require a running GIMP instance.

At minimum:

### Layer selection

```text
test_exact_theme_match()
test_missing_theme_uses_fallback()
test_exact_name_match()
test_missing_name_uses_fallback()
test_empty_theme_rejected()
test_empty_name_rejected()
```

### Title parsing

```text
test_simple_title()
test_title_with_newline()
test_multiple_text_runs()
test_empty_text_run()
test_rich_text_json()
test_invalid_rich_text_json()
```

### Input validation

```text
test_missing_template()
test_missing_output()
test_missing_title()
```

### Application service

Mock the GIMP API and verify:

```text
request
 ↓
select theme
 ↓
select name
 ↓
render title
 ↓
export
```

---

# 35. Testing GIMP-Specific Code

Where possible, isolate GIMP API interaction behind interfaces that can be mocked.

Do not require GIMP to run for every unit test.

For example:

```python
class GimpLayerManager:
    ...
```

can be replaced in tests with:

```python
FakeLayerManager
```

Integration tests that require GIMP should be separate.

---

# 36. Manual Test Matrix

After implementation, manually verify:

| Test                        | Expected                |
| --------------------------- | ----------------------- |
| Existing GUI workflow       | Works exactly as before |
| Existing Theme              | Correct layer selected  |
| Existing Name               | Correct layer selected  |
| New Theme layer             | Appears automatically   |
| New Name layer              | Appears automatically   |
| Unknown Theme               | Theme fallback          |
| Unknown Name                | Name fallback           |
| Simple CLI title            | Works                   |
| CLI title with newline      | Two-line title          |
| Rich title with two fonts   | Correct fonts           |
| Rich title with 3+ runs     | Correct                 |
| Existing template unchanged | Yes                     |
| PNG export                  | Works                   |
| CLI repeated twice          | Same result             |
| Invalid template            | Clear error             |
| Invalid rich text           | Clear error             |

---

# 37. Rich Text Acceptance Criteria

The rich-text implementation is considered complete when this conceptual input:

```json
{
  "runs": [
    {
      "text": "Woodworking\n",
      "font": "Font A",
      "size": 72
    },
    {
      "text": "Course",
      "font": "Font B",
      "size": 64
    }
  ]
}
```

produces a thumbnail in which:

```text
Woodworking
Course
```

is rendered as two lines and the two text runs use their specified fonts/sizes, subject to the actual capabilities of GIMP 3.

If GIMP 3 cannot reliably represent this as one text layer, use multiple text layers or another technically sound mechanism.

Document the chosen implementation and why it was selected.

---

# 38. Important Rich Text Constraint

Do not rasterize the entire title simply to make rich text possible unless there is no viable alternative.

Prefer actual GIMP text layers/objects so that:

- text remains editable
- fonts remain meaningful
- future modifications remain possible
- the template remains maintainable

If a limitation of the GIMP API makes this impossible, document the limitation explicitly and choose the least destructive workaround.

---

# 39. CLI Acceptance Criteria

The final plugin must support an automation workflow equivalent to:

```text
Input:
    template.xcf
    title
    theme
    name
    output.png

Processing:
    load template
    select theme
    select name
    render title
    export PNG

Output:
    output.png
```

The exact invocation syntax should follow GIMP 3's supported plugin/PDB/batch architecture.

The CLI must not require a human to interact with the GUI.

---

# 40. Do Not Duplicate Logic

The following must have exactly one implementation each:

```text
Theme discovery
Name discovery
Theme selection
Name selection
Fallback handling
Title rendering
Template processing
PNG export
```

Both GUI and CLI must call these shared implementations.

---

# 41. Refactoring Rules

During refactoring:

### Remove

- duplicated code
- unused imports
- dead code
- broad exception handlers
- unexplained magic numbers
- unnecessary global state
- duplicated GIMP API calls
- GUI code mixed with image manipulation
- hard-coded assumptions that can be safely abstracted

### Improve

- naming
- type hints
- error handling
- logging
- function boundaries
- documentation
- API usage
- resource management

### Avoid

- unnecessary frameworks
- excessive abstraction
- rewriting working behavior for stylistic reasons
- changing the template structure without necessity
- changing the visual output unintentionally

---

# 42. GIMP API Verification

Because the original plugin was written without extensive GIMP API knowledge, specifically audit:

- procedure registration
- procedure arguments
- image/layer APIs
- layer group traversal
- visibility handling
- text layer APIs
- text formatting APIs
- image loading
- image exporting
- object/reference lifetime
- error/status handling

Use the actual GIMP 3 API documentation and/or installed GIMP API definitions rather than relying on GIMP 2 examples.

Do not copy old GIMP 2 API patterns into the refactored implementation without verifying that they are valid for GIMP 3.

---

# 43. Documentation

Update/create `README.md`.

It must document:

## GUI usage

How to use the plugin normally.

## CLI usage

How to invoke the plugin through GIMP 3.

Include a simple example.

## Rich text

Explain both simple titles and rich-text input.

## Template structure

Document the expected:

```text
Themes
Names
Title
```

groups/layers.

## Fallback behavior

Explain how missing Theme/Name values are handled.

## Development

Explain the source structure and how to run tests.

---

# 44. Implementation Process for Claude Code

Follow this order.

## Phase 1 — Reconnaissance

Do not change code.

Inspect:

- repository
- plugin source
- GIMP registration
- GUI
- layer traversal
- title implementation
- export implementation

Produce a short architecture assessment.

Identify:

```text
Current entry point:
Current GIMP API:
Current GUI:
Theme mechanism:
Name mechanism:
Fallback mechanism:
Title mechanism:
Export mechanism:
Potential bugs:
```

---

## Phase 2 — Refactor Core

Extract:

```text
data models
application service
layer selection
fallback handling
export
```

Do not change behavior intentionally.

Run tests/manual checks.

---

## Phase 3 — GUI Adapter

Move existing GUI behavior onto the new application service.

The GUI should remain visually/functionally equivalent unless a change is required for rich text.

---

## Phase 4 — CLI

Implement the CLI/non-interactive entry point.

Verify:

```text
CLI → Application Service → GIMP
```

works without displaying the existing dialog.

---

## Phase 5 — Rich Text

Implement the structured title model.

Implement newline support.

Implement multi-font rendering using the best supported GIMP 3 mechanism.

Keep simple titles backward compatible.

---

## Phase 6 — Robustness Audit

Review:

- exceptions
- GIMP object lifecycle
- layer visibility
- missing groups
- missing fallback layers
- missing title layer
- invalid paths
- export failures
- repeated execution

Fix genuine bugs and document assumptions.

---

## Phase 7 — Testing

Run:

```text
unit tests
```

and the manual test matrix.

---

## Phase 8 — Documentation

Update README with the actual discovered architecture and actual CLI invocation.

---

# 45. Definition of Done

The plugin is complete when all of the following are true:

### Existing functionality

- GUI still works.
- Theme list is dynamically generated.
- Name list is dynamically generated.
- Theme fallback works.
- Name fallback works.
- Existing templates remain usable.
- Existing output behavior is preserved.

### CLI

- Plugin can be invoked without GUI interaction.
- Title, Theme and Name can be provided programmatically.
- Template and output paths can be specified.
- CLI returns meaningful exit status.
- Errors are machine-readable enough for automation/logging.

### Rich text

- Newlines work.
- Multiple fonts can be used.
- Multiple text runs are supported.
- The implementation uses actual GIMP text functionality where possible.
- Existing simple titles still work.

### Code quality

- GUI and CLI share the same core implementation.
- GIMP-specific functionality is isolated.
- Layer-selection logic exists only once.
- Fallback logic exists only once.
- Error handling is explicit.
- No broad silent exception handling remains.
- Obvious dead code and duplicated logic are removed.
- Code is typed and documented where useful.

### Reliability

- Original XCF template is not accidentally modified.
- Repeated execution is safe.
- Output is verified.
- Resources are cleaned up.
- CLI execution can be run unattended.

---

# 46. Final Instruction to Claude Code

Do not treat this as a greenfield plugin rewrite.

The existing plugin is the source of truth for current behavior.

Your first task is to understand it.

Your second task is to refactor it without breaking that behavior.

Your third task is to expose the same functionality through a non-interactive CLI.

Your fourth task is to extend the title system to support rich text and newlines.

When a choice must be made between:

```text
quick workaround
```

and:

```text
clean reusable architecture
```

prefer the reusable architecture, provided it does not unnecessarily complicate the plugin.

When a GIMP API behavior is uncertain, inspect the actual GIMP 3 API/documentation rather than assuming GIMP 2 behavior.

Do not silently work around errors.

Do not duplicate functionality between GUI and CLI.

At the end, provide a concise implementation report containing:

1. What was changed.
2. Existing bugs discovered and fixed.
3. GIMP 3 API issues discovered.
4. CLI invocation syntax.
5. Rich-text input syntax.
6. Any limitations.
7. Tests performed.
8. Any remaining manual steps.
