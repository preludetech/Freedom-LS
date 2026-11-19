# QA layout probe and visual review

## Capturing screenshots

`browser_take_screenshot` honours the server's `--output-dir` only for its **default** filename. A
custom `filename` is written relative to the server's working directory instead, so it would miss
the `Screenshot directory` and break Step 10. Therefore:

- Call `browser_take_screenshot` **without** a `filename` argument. The server writes a default-named
  file (`page-<timestamp>.png`) into the `Screenshot directory`.
- Read the saved path from the tool response and record only its **basename** in the scratch record's
  `screenshot_path`. Step 10 moves the file into `<spec-dir>/screenshots/`, so the report links it as
  `![](screenshots/<basename>.png)`.

## Layout probe

The probe catches a header that does not line up with the content under it, a sidebar that has lost
its column, a region spilling past the viewport and regions drawn over each other. It measures
**ink**: text and anything with a border, background or replaced content. Whatever an ancestor's
`overflow`, `clip` or `clip-path` cuts off does not count, so an ellipsis-truncated label, a
screen-reader-only span or a table inside a horizontal scroll region is not overflow. The document
`scrollWidth` check is separate.

**Load it once**, before this step's first screenshot, as a solo call. Call
`<prefix>browser_run_code_unsafe` with:

`async (page) => { await page.context().addInitScript({ path: '<PROJECT_ROOT>/claude_plugins/sdd/resources/qa_layout_probe.js' }); }`

Every page the browser opens from then on defines `window.__qaLayoutProbe`, so navigate to the
first page under test **after** this call. When `PLUGINS_ROOT` is not `.`, the path takes the
`<PLUGINS_ROOT>/` prefix as in Rule 3b.

**Per-run capture check (mandatory):** the Playwright MCP server is unpinned, so its
behaviour can change between runs. Right after loading the probe, take one no-`filename` screenshot
of the first page under test and confirm that a default-named file lands in the `Screenshot
directory` **and** that no image bytes come back in the tool response. If bytes are returned, or no
file is written, stop and report it; do not trust the rest of the run. If the file lands somewhere
else entirely, find the actual write location and pass that to Step 10. That shot is a screenshot
of a page like any other: it gets the screenshot prep, the probe, the visual review and its own
`layout` record, and a fault it shows is a bug.

## Before every screenshot: clear dev tooling

Carry out the `Screenshot prep` instruction before each screenshot, and check its result in the
shot: dev tooling covering the page is a broken screenshot. A blank value means no prep.

**Run the probe after every screenshot of a page**, at every viewport, with `<prefix>browser_evaluate`:

`() => window.__qaLayoutProbe(<Layout regions>)`

`<Layout regions>` is the config value pasted literally, or `{}` when it is blank, which leaves only
the overflow check. Append one record per page and viewport:

```json
{"type": "layout", "test_id": "1.1", "viewport": "desktop", "url": "/path", "screenshot_path": "page-<timestamp>.png", "status": "pass|fail", "flags": ["…"]}
```

`status` is `fail` when `flags` is non-empty. A `missing` region on a page that has none (a page
outside the shell the selectors name) is not a flag. A layout failure is a bug like any other,
whether or not this branch introduced it.

## Visual review

The probe does not replace looking. For every screenshot, check each of these and record any
concern as a failing `test` record, never only in its notes:

- **Shell**: the navigation, the header and the content sit where the shell puts them at this
  viewport: a navigation column stays a column beside the content, a navigation bar stays a bar.
  Navigation drawn above the content, across the page's width or missing is a bug, never the
  page's look.
- **Alignment**: the page header, the content under it and the footer actions share a left edge,
  or are deliberately centred together.
- **Consistency with siblings**: pages in the same shell (every page of one player, one panel, one
  wizard) place their header and content the same way. Compare with the sibling pages already
  shot this run: one page that sits differently from the rest is a bug even if it looks fine alone,
  unless the spec documents or rule files describe the difference (Rule 5).
- **Space**: no region is squeezed, clipped or cut off, and no large gap opens that the
  rest of the shell does not have.
- **Cover**: nothing is hidden under dev tooling, a sticky bar or another region.
- **Fit**: a dialog, sheet, table or fixed bar stays inside the viewport at every width, title
  and every button included.
- **Project checklist**: every line under a `## Visual checklist` heading in each file listed
  under `## Rule Files`. A file without that heading contributes nothing. A line that fails is a
  failing `test` record like any other.

When a page looks wrong and you cannot tell whether it is intended, read what the spec documents
and rule files say about it first (Rule 5): a look they describe is intended, a pass. When they are
silent, compare it with the most recent
screenshot of the same page under `spec_dd/3. done/*/screenshots/`. Unchanged since then means
the look predates this branch. That is a reason to name it as pre-existing in the record, not to
pass it.
