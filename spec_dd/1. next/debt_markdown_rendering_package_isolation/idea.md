# Debt: package isolation — remove unnecessary cross-app (test) dependencies

> **Consolidated debt spec.** Folds in the former
> `debt_remove_unnecessary_app_dependencies` idea ("examine the app dependency map
> via `/app_map`, see what problems exist, clean them up"). That general directive
> lives here now, with `markdown_rendering → content_engine` as the fully-analysed
> flagship case.

## Rule

An app whose **runtime** does not depend on another app (no solid arrow in
`docs/app_structure.md`) should not have its **tests** depend on that app either
(no dashed arrow). Every such test-only edge is a package-isolation leak: it makes
an otherwise-independent app's tests unrunnable — or, if the other app is
optional, abortable — in a context that omits the other app, and it muddies the
layering. Classify each edge *inherent* (genuinely exercises both apps together,
or needs the other app's model with no lighter substitute) vs *incidental*
(convenience use of a factory/model the app itself doesn't depend on); **remove
the incidental ones** (rework to the app's own models / a local fixture / a stub,
or relocate misplaced tests to the app they belong to). Don't invent throwaway
models or undertake large refactors just to purify the graph — "inherent" is a
legitimate verdict.

## General scope (folded in from `debt_remove_unnecessary_app_dependencies`)

Run `/app_map`, then audit **every** edge in `docs/app_structure.md` — solid
(runtime) and dashed (test-only) — for unnecessary coupling, applying the rule
above. The map drifts, so grep the tree; it is authoritative (e.g. it currently
omits the live `course_access → course_applications` test edge). Record a
keep/remove verdict per edge and remove the incidental ones. Regenerate the map
afterwards.

Most of the **test-only** surface was already audited in `fls-test-portability-part1`
(its Task 0), which judged all eight dashed edges: seven inherent (kept), one
incidental — `markdown_rendering → content_engine` — deferred here. That audit is
the starting point; this spec picks up the deferred item plus any **runtime**-edge
cleanup the general pass surfaces.

## Flagship case: `markdown_rendering → content_engine`

`markdown_rendering` is a generic markdown→HTML app with **zero runtime reference**
to `content_engine`, `File`, or the `c-picture`/`c-card` cotton components (all
defined in `content_engine`) — confirmed:
`grep -rn "content_engine\|c-picture\|File" freedom_ls/markdown_rendering --include="*.py"`
outside `tests/` returns nothing. The dependency map shows only a **dashed reverse
arrow** `markdown_rendering -.-> content_engine` (a lower-layer app's tests
reaching *up* into the higher-layer app that depends on it at runtime).

The coupling lives entirely in `markdown_rendering/tests/test_markdown_utils.py`:

1. **`TestInjectTableCaption` (~lines 872–917)** — pure unit tests of
   `content_engine.templatetags.content_tags.inject_table_caption`. They call the
   filter **directly and never touch `render_markdown`**. Unambiguously misplaced
   `content_engine` unit tests.
2. **c-picture tests inside `TestRenderMarkdownCustomTags`** (`_make_image_file`
   helper ~line 306; `test_c_picture_*`/grid cases ~318–476) and **`TestCCard`
   (~716–822)** — create a `content_engine` `File` row and assert rendered
   `c-picture`/`c-card` HTML. They verify `content_engine` component output, using
   `render_markdown` only as the entry point.

### Why it was deferred out of Part 1

Removing it is a **relocation of test code between apps**, and the c-picture/c-card
cases sit inside a mixed 628-line `TestRenderMarkdownCustomTags` class, so clean
extraction exceeds Part 1's "quiet the noise" scope. It carries **no portability
risk** — `content_engine` is core and always installed, and the imports are
function-local, so they never abort collection.

### Desired end state

- `grep -rn content_engine freedom_ls/markdown_rendering/tests/` returns nothing.
- The `markdown_rendering -.-> content_engine` dashed edge is gone from a
  regenerated `docs/app_structure.md`.
- `markdown_rendering`'s own tests cover the generic pipeline (custom-tag
  mechanism, sanitiser, etc.) using **generic/stub tags**, not `content_engine`'s
  real components.

### Proposed approach

- **`TestInjectTableCaption` → relocate wholesale** into `content_engine/tests/`
  (new `test_content_tags.py`, or an existing content-tags module). Zero
  `render_markdown` involvement — a clean move.
- **c-picture / c-card component-output tests → relocate** alongside it. A
  `content_engine` test calling `render_markdown` is a legitimate *forward* edge
  (`content_engine` already depends on `markdown_rendering` at runtime).
- **Judgment call while splitting the mixed class:** a test that verifies
  `markdown_rendering`'s **own pipeline/sanitiser** using a component merely as an
  input vehicle (e.g. the "attributes survive the markdown *sanitiser*" case,
  ~line 361) is a genuine `markdown_rendering` test — **keep it in place but
  rewrite it against a generic/stub tag** so the residual coupling is gone. Only
  relocate tests whose assertions are about `content_engine` component output.
- Follow TDD: relocated tests green in their new home, asserting the same
  behaviour (capture green before the move, re-run after).

## Other known item: `accounts` as the test-support hub

`SiteFactory` wraps the Django builtin `Site` but lives in `accounts`, so
`webhooks`, `site_aware_models` and many others import it from there — which is why
`accounts` looks like a foundational test dependency. Relocating it (e.g. to
`site_aware_models`, or a shared test-support module) removes a swathe of dashed
`… → accounts` edges. No portability payoff (`accounts` is always installed), so
it's low urgency, but it's the biggest single lever for tidying the test-dependency
graph. Assess as part of the general pass.

## Notes

- Method + factory/fixture/stub conventions: the `testing` skill.
- The Part-1 audit (source of the deferred item + the seven inherent keeps) is in
  `fls-test-portability-part1` spec §4e / plan Task 0.
</content>
