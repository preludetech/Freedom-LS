# Research: UX patterns for the word-plus-speaker-button control

Topic: ux_patterns. Provenance: the patterns in sections 1 to 5 come from background knowledge of common practice (no live web fetch; WCAG and MDN URLs are the standard references, verify before quoting). Sections 6 and 7 are from the codebase and are checked, with file:line.

## 1. The pattern in the wild

- **Dictionary sites** (Merriam-Webster, Oxford, Cambridge, Wiktionary): the headword or its IPA sits beside a small speaker icon button. The click plays one clip and nothing else changes. The word stays visible text; the icon is the only control. Respelling or IPA is plain text beside it, often in a muted style. Wiktionary shows `IPA: /ˈæl.fə/` plus a small play control. Merriam-Webster shows the respelling in a lighter style next to the speaker.
- **Language apps** (Duolingo, Memrise, Quizlet): a round or bare speaker icon beside the term. Duolingo adds a tortoise "slow" variant. The tap target is larger than the glyph.
- **Common structure**: `[word] [speaker]` on one line, the word first (reading order), the button after. The pair never wraps apart (use `inline-flex`/`whitespace-nowrap`, or `flex items-center gap-2`).
- **Icon-only versus word-as-button**: two variants exist. (a) A word plus a separate small icon button (the user's choice here). (b) The whole word is the button (a large tap area, good on phones, but the word then looks like a link). The user chose (a). To keep a generous touch target while the glyph stays small, give the icon button a `size-10` or `min-h-11 min-w-11` hit box (WCAG 2.2 SC 2.5.8 sets a 24 CSS px minimum; Apple and Material guidance is 44 to 48 px) with a `size-5` glyph. https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html

## 2. States

| State | Visual | Semantics | Notes |
|---|---|---|---|
| Idle | Speaker glyph, muted or primary colour | `<button type="button" aria-label="Play pronunciation of Alpha">` | Never plays on load. |
| Loading | The glyph swaps for a spinner while the file is fetched on first play (preload is `none`) | `aria-busy="true"` on the button; keep the same accessible name | Show it only after about 150 ms, otherwise a cached clip flickers. Clips are about 8 KB, so loading is usually invisible; the state matters mostly for slow mobile networks. |
| Playing | Glyph swaps for a "sound on / waves" or a stop/pause glyph; button gets a tinted background | `aria-pressed="true"`, or switch the label to "Stop pronunciation of Alpha". Pick one: do not change the name and use `aria-pressed` together (that announces "Stop ..., pressed"). | A second click either stops or restarts. Dictionary sites restart; stopping is the clearer toggle. Spec must choose. Only one clip at a time: starting a clip stops the previous one, whose button returns to idle. |
| Ended | Back to idle | `aria-pressed="false"` | Listen for the `ended` event. |
| Error | Warning glyph or retry glyph, error colour, plus a visible text such as "Audio unavailable" next to the word (colour alone fails WCAG 1.4.1) | A polite live region (`role="status"`) so a screen reader hears it; the button stays enabled so the learner can retry | Do not disable the button: with an expired signed URL the user's answer is to refetch a fresh URL on error (user decision), so the click after an error is the retry. Treat the first `error` as "refetch URL once, retry silently", show the error state only if the refetch also fails. https://developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement/error_event |
| Disabled/unsupported | Rare. If the file is missing at render time, use the existing red "not found" box instead of a button. | | See section 6. |

Rules common to all states: the focus style must remain visible in every state; the state change must not move the word (fixed-size icon slot, so the layout does not jump); the state must be conveyed by shape or text as well as colour; honour `prefers-reduced-motion` (a spinning icon is fine, but a pulsing "playing" ring should be switched off). https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html

Accessible name: "Play pronunciation of Alpha" contains the visible word, satisfying 2.5.3 Label in Name (the visible label is the word beside the button, so the name should contain it). An optional respelling is not repeated in the name.

## 3. Optional respelling

- Typical placements: (1) after the word in muted smaller text, `Alpha  AL FAH  [speaker]`; (2) in brackets or slashes, `Alpha (AL-fah)`; (3) below the word as a second line (a caption). Dictionaries put the respelling directly after the headword and the speaker after that, or the speaker first.
- For a phone-width grid cell, put it **below the word** (second line, `text-sm text-muted`). It keeps the word-and-icon row short and lets long respellings wrap without pushing the icon off the row. In a table, put it in its own column or under the word in the same cell.
- Respellings are the text alternative for WCAG 1.2.1, so they must be real text (not an image and not `aria-hidden`). Do not set the `lang` of an English respelling to something else. Respellings use capitals and hyphens by convention ("AL FAH", "BRAH VOH"); render them exactly as authored, with no case transformation, and give them a muted style that still passes 4.5:1 on the surface (the brand Slate on Chalk is 7.1:1, see section 6).
- Absent respelling: render nothing (no empty element, no placeholder), and the row collapses to word plus button.
- Do not add the respelling to the button's accessible name; place it in the DOM right after the word so reading order is word, respelling, button. Optionally link it with `aria-describedby` on the button so a screen reader can read it on focus.
- Visible word is required: the idea names the visible word as the text alternative. Recommend `label` as the required visible text and no icon-only mode, because an icon-only control has no visible text alternative.

## 4. Layout at phone width (375 px) in grids and tables

- The existing grid is one column on phones, 2 at `sm`, 3 or 4 at `lg` (`grid.html:20-26`). Twenty-six items in one column at 375 px is a long scroll (about 26 x 48 px = 1250 px), which is acceptable but tall. Two columns at phone width suits word-plus-button, because each cell holds only about 10 characters plus a 44 px button (a 375 px screen gives about 160 px per cell after padding). A long respelling then wraps. This is a question for the spec: the grid's `columns` whitelist gives 1 column on phones regardless, so a letter list will be one column on a phone unless a phone-width option is added. Do not add one unless asked (CLAUDE.md "don't build functionality not requested"); note it as an option.
- Row pattern that works in a one-column list: `flex items-center justify-between` (word left, speaker right, so all buttons line up in one column on the right edge and the targets are easy to hit with a thumb). Alternatively `justify-start` with the button directly after the word. Brand rule "things line up: items of one kind sit in one column" (`.claude/skills/brand-guidelines/visual.md:Things line up`) favours buttons in a consistent column; a word-then-icon with `gap-2` makes the icons ragged because words differ in width. In a table, put the button in its own narrow column to keep that alignment for free.
- Tables: the base layer styles tables with no classes. A three-column table (letter, word with respelling, play) at 375 px fits: "A | Alpha AL FAH | [btn]". Do not let the button column wrap; give it `w-12`/`whitespace-nowrap`.
- Cell hit area: the 44 px target in a table row of normal height means rows are at least 44 px tall. Accept it, or keep the glyph at `size-5` with padding to meet the 24 px minimum at least.
- Avoid a box around each item (brand rule: "no box around each item in a group"); the widget sits on the page surface with space between items.
- Inline use in prose ("pronounced Alpha [speaker] in the ICAO standard") needs an inline variant: `inline-flex items-baseline`, a glyph that scales with `1em`. The list case is the main one; say in the spec whether an inline variant is in scope.
- At 375 px the existing `c-file-download` wrapper has `my-6` (`file-download.html:15`); inside a grid, `grid.html` zeroes the child's outer margin with `[&>*]:my-0!` (line 21), so a `c-audio` root element that is a direct child gets its margin zeroed. Put the root margin on the root element, as the other components do, so the grid override works. A nested wrapper (a `<span>` inside a `<div>`) would escape it.

## 5. Behaviour patterns worth borrowing

- One shared audio object (or a registry) so starting a clip stops the other: the idea already requires it. Wrapping the state in an Alpine store keyed by clip id lets the other buttons return to idle.
- Create the `Audio` or set `src` on first click (satisfies "never fetch all on load", and iOS needs the play call to be in the click handler). Loading state starts there. A fetch for a fresh signed URL on error then re-calls `play()`, which iOS may reject if it is no longer inside the gesture; the spec should say a second tap is acceptable after an error refetch, which is why the button must stay enabled.
- Keyboard: a native `<button>` gives Tab, Enter and Space. Focus stays on the button when it changes state (do not re-render the node; toggle the icon spans). Do not move focus.
- Do not use `title` as the only hint; a visible label is already there.
- Announce: no live announcement on play (the sound is the feedback); announce only errors.

## 6. FLS conventions the widget must fit (checked)

- **Icons**: only through `<c-icon name="...">` with a semantic name from `SEMANTIC_ICON_NAMES` (`claude_plugins/fls-dev/skills/icon-usage/SKILL.md:9`). `freedom_ls/icons/semantic_names.py:1-73` has no play, speaker, volume, pause, stop or audio name. It does have `loading` (line 50), `error` and `warning` (18-19), `retry` (32 area, under Actions), `paused` (27) and `in_progress`. So the spec must add semantic names (for example `audio_play` for the idle glyph, `audio_playing` for the playing glyph; reuse `loading` for the spinner and `error` or `retry` for failure), following `claude_plugins/fls-dev/skills/icon-usage/resources/configuring-icons.md`, and map them in the Heroicons set (`speaker-wave` is the natural idle glyph, `stop` or `pause` the playing one; verify the exact Heroicons names). No raw SVG, Unicode glyph or Font Awesome class.
- **Sizes**: `size-5` for buttons (default), `size-4` for small UI, `size-8` for loading spinners (icon-usage SKILL "Sizing"). A spinner inside a small button should be `size-5` with `animate-spin`, matching `button.html:61` (`<c-icon name="loading" class="size-5 animate-spin" />`). `class` replaces the default size, so pass the size every time.
- **Icon-only control accessible name**: put `aria-label` on the button, not the icon; the icon stays decorative (icon-usage SKILL "Accessibility"). With a visible word beside it, the label is "Play pronunciation of {word}".
- **Toggling icons with Alpine**: icons are server-rendered, so toggle `x-show` on wrapper spans, with `x-cloak` on the initially hidden ones (icon-usage SKILL "Toggling with Alpine.js"). The three states therefore need three or four pre-rendered spans (idle, loading, playing, error). Methods and property names only in `x-*` attributes (CSP build, idea.md "What is settled").
- **Button component**: `<c-button>` (`freedom_ls/base/templates/cotton/button.html`) takes `icon_left`, `aria_label`, `size="small"`, `variant`; its icon is `size-5` with `mr-2` margin and it adds `aria-hidden` (lines 11, 17, 33, 39, 54). It has no icon-only mode: `icon_left` always adds `mr-2`, and the box has horizontal padding, so a square icon-only button is not what it gives. Options for the spec: (a) `<c-button variant="ghost" size="small" aria_label="...">` with the icon in the slot (it then can't be toggled by `x-show` on its icon, since the slot is not Alpine-aware... it is, because slot content is plain HTML, so `x-show` spans in the slot work; but `x-bind:aria-pressed` needs attributes on the `<button>` that `c-button` may not pass through: check for an attrs passthrough before relying on it); (b) a bespoke `<button>` in `audio.html` using the `.btn` classes or utilities. The brand rule says "reach for the component", so check (a) first and say in the spec if it cannot carry the Alpine attributes. `button.html:73-75` lists variants including `ghost`.
- **Focus**: the theme has `--color-focus-ring: var(--color-primary)` (`freedom_ls/themes/default/static/themes/default/theme.css:133`). Use the existing focus-visible styling of `.btn` rather than a new rule; do not write unlayered CSS and do not add a per-widget stylesheet (`claude_plugins/django-stack/skills/frontend-styling/SKILL.md:24-31`).
- **Colour tokens** (brand `visual.md` Palette): word in `text-on-surface`, respelling in `text-muted` (Slate, 7.1:1 on Chalk), idle icon `text-primary` or `text-muted`, playing state `bg-primary text-on-primary` or a `bg-primary/10` tint, error text `text-error` (5.0:1 on white). No raw palette utilities (`bg-blue-600`; the icon-usage example `text-blue-500` is only an example, the frontend-styling rule forbids raw palette utilities where a token exists). Sand and Forest fail as text, so do not use them for the error or success text.
- **Not-found box**: the existing red box is `my-6 p-4 bg-error/10 border border-error/20 rounded-lg` with `<p class="text-error">File not found: {{ src }}</p>` (`file-download.html:25-29`; the same shape appears in `picture.html`, `pdf-embed.html`). Reuse the wording "File not found: {{ src }}".
- **Runtime error** is a different case from "not found" (the file row exists but the fetch fails): a runtime state on the button, not the red box. Brand says a status that names the state of a record is a badge; a transient playback failure is better as short inline text (`text-error text-sm`) than a `c-panel-status-badge`. A `c-chip` is for tags and levels, not errors.
- **One-line label rule**: "A button label fits on one line down to 375 px" and "Buttons of one size are one height" (visual.md). The word is not the button label here, but keep `whitespace-nowrap` on the word-plus-icon so the pair doesn't break. Phonetic words are at most 8 characters ("Foxtrot", "Juliett"), so one line fits.
- **Spacing**: items separated by space, no per-item box, things line up in one column (visual.md UI principles 3 and 4).
- **Dark mode / themes**: everything through role tokens so other themes apply (visual.md intro).
- **Voice**: error text uses the project voice (`.claude/skills/brand-guidelines/voice.md`, not read in detail here); keep it to a plain sentence such as "Audio unavailable. Try again."

## 7. Recommended design (for the spec to accept or change)

1. Row: `[word] [respelling, muted, optional, below or after] [speaker button]`, in a `flex items-center gap-2` row, `whitespace-nowrap` on the word and button. The `label` text is required and visible.
2. Button: a real `<button type="button">`, `aria-label="Play pronunciation of {label}"`, 44 px hit box, `size-5` glyph, ghost style, `.btn` focus ring.
3. States via Alpine: idle, loading, playing, error, each a pre-rendered `<c-icon>` span toggled by `x-show`; `aria-busy` while loading; `aria-pressed` while playing (one convention only); error text beside the word with `role="status"`; the button stays enabled after an error so the click retries with a fresh signed URL.
4. Only one clip plays at a time; ending or stopping returns the button to idle.
5. In a table, give the button its own narrow column; in a grid, the cell is the row from item 1. Phones get one column from the existing `grid` unless the spec adds a phone-width option.
6. Add the audio semantic names to `SEMANTIC_ICON_NAMES` and the icon-set mapping.

## 8. Open questions the spec must settle

- Second click while playing: stop or restart? (Recommend stop, with `aria-pressed`.)
- Respelling placement: after the word or on its own line below (recommend below in cells, after the word inline).
- Inline variant for use in prose: in scope or not.
- Whether `c-button` can carry the Alpine attributes and a square icon-only look, or `audio.html` needs its own `<button>`.
- Whether to add a two-column phone option to `c-grid` (not requested, so probably not).
- Icon names for the new semantic icons and the Heroicons mapping.

## Sources

- WCAG 2.2 Target Size (Minimum): https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
- WCAG 2.2 Use of Color: https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html
- WCAG 2.2 Label in Name: https://www.w3.org/WAI/WCAG22/Understanding/label-in-name.html
- MDN media `error` event: https://developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement/error_event
- WAI-ARIA APG button pattern (toggle with `aria-pressed`): https://www.w3.org/WAI/ARIA/apg/patterns/button/
- Codebase: `freedom_ls/icons/semantic_names.py`, `freedom_ls/base/templates/cotton/button.html`, `freedom_ls/content_engine/templates/cotton/grid.html`, `freedom_ls/content_engine/templates/cotton/file-download.html`, `freedom_ls/themes/default/static/themes/default/theme.css`, `.claude/skills/brand-guidelines/visual.md`, `claude_plugins/fls-dev/skills/icon-usage/SKILL.md`, `claude_plugins/fls-dev/skills/frontend-styling/SKILL.md`, `claude_plugins/django-stack/skills/frontend-styling/SKILL.md`.

status: ok
