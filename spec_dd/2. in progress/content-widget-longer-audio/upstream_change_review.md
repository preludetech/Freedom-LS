# Upstream-change review: content-widget-longer-audio

direction: changed

## What main gained
Main gained the `c-audio-reveal` widget (spec `content-widget-sayit-reveal-2-say-it-reveal`, now in `spec_dd/3. done/`). Its Alpine side refactored `audioFile` in `freedom_ls/content_engine/static/content_engine/js/alpine-components.js` into a shared `audioPlayer()` factory used by `audioFile` and `audioReveal`. That is an implementation overlap with this branch's `activeAudio` takeover edit to `audioFile`. It is a merge and regression concern, not a direction change.

Main also added a "one markdown pass for slot widget bodies" convention. `MARKDOWN_BODY_TAGS` in `freedom_ls/markdown_rendering/config.py` and `markdown_utils.py` converts the body of each listed tag once, at the top level. A slot widget's template must use `{% markdown_body slot markdown %}` (in `content_tags.py`) and must never use `{% markdown slot %}`. Under a parent slot widget the body stays raw and is converted once. `accordion`, `admonition`, `card`, `flashcard`, `pull-quote` and `table` were all migrated. `docs/how tos/custom-content-widgets.md` and `claude_plugins/fls-dev/resources/markdown_content.md` now say any widget can nest inside a slot widget. `test_markdown_utils.py` has an invariant that every slot-using widget is listed in `MARKDOWN_BODY_TAGS`. I verified all of this in the repo.

`c-audio` and `c-flashcard` also changed: `c-audio` now plays inside a flashcard face, via a shared `audio_card_body.html` partial. The icons files, `settings_base.py` allowlist and `widget-reference` docs overlap with this branch's edits. They are textual conflicts to check, not decisions.

## Why it matters for this spec
This branch's `freedom_ls/content_engine/templates/cotton/audio-clip.html` still renders its transcript with `{% markdown slot %}` and does not declare `c-audio-clip` as a slot widget. That contradicts the new convention, and the invariant test would flag it. The nesting decision rests on the old mechanism:
- `1. spec.md`, "Widget template" (transcript bullet: "The panel renders `{% markdown slot %}`") assumes the old pattern.
- `1. spec.md`, "Nesting limits" says the clip does not work inside `c-table`, `c-accordion`, `c-admonition`, `c-flashcard` or `c-card`, and that file-resolving widgets in its transcript fail. It says both limits come from `{% markdown slot %}` rendering without `content_instance`. That cause is now removed on main.
- `1. spec.md`, "Scope" and "Documentation and downstream" carry the same nesting claim into the widget-reference quirk and `c-audio-clip.md`.
- `2. plan.md`: the template batch, the Playwright batch and the docs batch carry the same nesting claim, and the spec's allowlist and markdown-body wiring omit `MARKDOWN_BODY_TAGS`.
- The implemented template batch (`audio-clip.html`) uses `{% markdown slot %}`.

The `audioFile` `activeAudio` takeover edit also touches code main refactored. Re-check that it still applies, and that `audioReveal` joins the one-sound-at-a-time handle. The done spec's `audioReveal` has its own one-at-a-time rule, so confirm the two do not diverge.

No done spec's decision is reopened. This spec adopts the convention.

## What to change
- `freedom_ls/content_engine/templates/cotton/audio-clip.html`: replace `{% markdown slot %}` with `{% markdown_body slot markdown %}`. Update its header comment to mention it. Check whether the template needs `markdown` as a variable (see `card.html` and `admonition.html`). Remove the "Do not nest" wording.
- `freedom_ls/markdown_rendering/config.py`: add `"c-audio-clip"` to the `MARKDOWN_BODY_TAGS` default tuple. This is required so the invariant test in `test_markdown_utils.py` passes.
- `1. spec.md`: change the transcript bullet to `{% markdown_body slot markdown %}`. Rewrite "Nesting limits" to say the clip nests inside slot widgets like any widget, and that a file-resolving widget in its transcript works. Keep the real limit that the clip's own `x-data` and `$id` are independent per instance. Update the "Markdown allowlist" section to list the `MARKDOWN_BODY_TAGS` entry. Fix "Documentation and downstream" so the `c-audio-clip.md` and `SKILL.md` quirk no longer states the nesting limits.
- `2. plan.md`: update the template batch and the docs batch to match. Drop any task or test that asserts the clip fails inside slot widgets. Add a render test that the clip nests in a slot widget (for example `c-accordion`) and that a `c-audio` or file-resolving widget in the transcript renders.
- `claude_plugins/fls-content/skills/widget-reference/SKILL.md` and `resources/c-audio-clip.md`: remove the nesting quirk, matching main's `c-audio` and `c-audio-reveal` docs.
- `claude_plugins/fls-dev/resources/markdown_content.md`, `docs/product/content-editing-workflow.md` and the upgrade notes: reconcile with main's text after the rebase. Make sure `c-audio-clip` appears in the widget list, the allowlist copy matches `config/settings_base.py`, and no "must not nest" wording remains.
- `alpine-components.js`: after the rebase, re-verify that the `audioFile` takeover edit and the `audioClip` registration sit correctly around `audioPlayer()`, and that `audioReveal` honours the shared `activeAudio` handle (or document why it does not). Re-run the existing `c-audio` and `c-audio-reveal` component and Playwright tests.
- `freedom_ls/content_engine/tests/demo_content/` and `demo_content/.../2. media/content.md`: re-check the audio counts against main's new `c-audio-reveal` demo section. The spec's "six audio widgets" figure may now be wrong.

status: ok
