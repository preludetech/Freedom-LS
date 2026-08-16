# Report fonts

The PDF report embeds its own fonts. It does not use system fonts: WeasyPrint substitutes
silently for a missing family and draws a `.notdef` box for a missing code point, and both are
invisible until somebody reads a printed report.

## What is here

| File | Family | Source | Licence |
|---|---|---|---|
| `Inter-Variable.ttf` | Inter | [google/fonts `ofl/inter`](https://github.com/google/fonts/tree/main/ofl/inter) | `Inter-OFL.txt` |
| `SourceSans3-Variable.ttf` | Source Sans 3 | [google/fonts `ofl/sourcesans3`](https://github.com/google/fonts/tree/main/ofl/sourcesans3) | `SourceSans3-OFL.txt` |
| `SourceCodePro-Variable.ttf` | Source Code Pro | [google/fonts `ofl/sourcecodepro`](https://github.com/google/fonts/tree/main/ofl/sourcecodepro) | `SourceCodePro-OFL.txt` |
| `DejaVuSans.ttf`, `DejaVuSans-Bold.ttf` | DejaVu Sans | DejaVu Fonts | `DejaVu-LICENSE.txt` |

Inter, Source Sans 3 and Source Code Pro are the typefaces the `brand-guidelines` skill names
for FreedomLS, so the report reads as the same product as the web interface.

The three brand files are the **upstream variable fonts, byte-for-byte unmodified** — only the
filenames differ, to keep the `[wght]` brackets out of static paths and URLs. WeasyPrint
instantiates the weight axis per `@font-face` rule, so one file serves every weight the report
asks for. They are shipped unmodified deliberately: the Source families reserve the name
"Source" under the SIL Open Font License, and an instanced copy would be a Modified Version that
could no longer carry that name.

DejaVu Sans is last in all three stacks and is the face that draws the status glyphs
(`✓ ✗ ▲ ● ○ —`). Keep it in any stack you configure, or supply a face that covers those code
points yourself — greyscale legibility depends on them.

## Replacing them in a downstream project

Nothing in `print.css` names a font. The report reads three stacks and a face list from settings,
the same way it reads its colours from the theme's CSS custom properties, so a project on its own
brand overrides them rather than forking a template:

```python
REPORTS_FONT_FACES = [
    {
        "family": "Acme Grotesk",
        "weight": "700",
        "style": "normal",
        "static_path": "acme/fonts/AcmeGrotesk-Bold.ttf",
    },
    # ... one entry per weight and style you use, plus a glyph-covering fallback
]
REPORTS_FONT_DISPLAY = '"Acme Grotesk", "DejaVu Sans", sans-serif'
REPORTS_FONT_BODY = '"Acme Text", "DejaVu Sans", sans-serif'
REPORTS_FONT_MONO = '"Acme Mono", "DejaVu Sans", monospace'
```

Each `static_path` is resolved through the staticfiles finders, so it can live in any app's
static directory or in `STATICFILES_DIRS`. A path that cannot be resolved is reported by
`manage.py check` as `freedom_ls_reports.W004` and raises when a report renders — the report
never quietly falls back to a substitute face.
