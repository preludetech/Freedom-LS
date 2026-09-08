# Research — the source design

The idea links
`https://claude.ai/design/p/019df696-b642-74bb-a97b-ad6a760b0491?file=Quiz+Start+-+First+Time.html`.
That URL is not fetchable by `WebFetch` (403) and is not an artifact URL. It **is** readable through
the `DesignSync` MCP tool, which reads the user's claude.ai design projects:

```
DesignSync method=list_files  projectId=019df696-b642-74bb-a97b-ad6a760b0491
DesignSync method=get_file    projectId=019df696-b642-74bb-a97b-ad6a760b0491  path=<path>
```

The artboard file itself is only a React harness. The design lives in:

| Path | Holds |
| --- | --- |
| `components/CheckinFirstTime.jsx` | `CheckinIntroFirst` (detailed) and `CheckinIntroFirstSimple` (simple), plus their mobile twins |
| `components/Checkin.jsx` | `CheckinIntro` — the returning-learner start screen, shown in the canvas "for comparison" |
| `styles-exam.css` | `.fc-exam-intro`, `.fc-exam-meta-grid`, `.fc-exam-cta-row`, `.fc-exam-start` |
| `styles-exam-checkin.css` | `.ck-welcome`, `.ck-reassure`, `.ck-prev` (previous attempts) |
| `styles-checkin-first.css` | `.ckf-steps`, `.ckf-covers`, and the whole `.ckfs` simple variant |

The canvas is built on the **first_class** theme's palette: design `--color-primary` is Deep Indigo
`#283593` and `--color-secondary` is Electric Teal `#00CEC9`, which are exactly
`freedom_ls/themes/first_class/static/themes/first_class/theme.css`. So the design's colours already
map onto FLS role tokens — see "Token mapping" below.

---

## The two start-screen variants

The artboard offers two, and they are genuinely different products.

### A. Detailed — `CheckinIntroFirst`

Top to bottom:

1. A "Back to section" text link with a left-arrow.
2. Eyebrow: a short rule (`.sep`, a 24px 1px bar) then mono uppercase tracking-wide label.
3. `h1` at 42px, display face, `-0.02em` tracking.
4. Standfirst paragraph, 17px, `max-width: 60ch`.
5. **Welcome banner** (`.ck-welcome`) — a 52px rounded-square badge in solid teal beside a heading
   and a sentence, on a panel with two soft radial washes (teal from the top-left, indigo from the
   bottom-right) over the elevated surface.
6. **Meta grid** (`.fc-exam-meta-grid`) — 4 equal cells in one bordered, rounded, overflow-hidden
   panel divided by 1px rules, *not* separate cards. Each cell: a 32px rounded icon tile, a 22px
   display-bold number, a 11px uppercase tracked label. Cells are Questions, "~10 min / Relaxed
   pace", Pages / "Short pages", "Unlimited / Tries".
7. **How it works** (`.ckf-steps`) — a mono uppercase section heading, then 3 bordered cards, each
   with a 38px rounded icon tile, a "Step N" mono label, a bold title and a sentence. Collapses to
   one column under 900px.
8. **What it covers** (`.ckf-covers`) — a bordered panel: heading + summary sentence on the left, a
   pill button on the right, then a wrap of pill tags.
9. **Reassurance chips** (`.ck-reassure`) — a wrapping row of pill chips in three tints: success,
   "calm" (teal at 10%), and neutral (grey).
10. **CTA row** (`.fc-exam-cta-row`) — top border, primary button, outlined secondary button, and a
    right-aligned mono meta line.

The returning-learner comparison (`CheckinIntro`) is the same page with the welcome banner reworded
and a **previous attempts** panel (`.ck-prev`) inserted before the CTA: a bordered panel with an
uppercase label, a summary line, a pill "View all" button, and rows carrying an attempt number, a
status pip, a date, a mono score and a caret.

### B. Simple — `CheckinIntroFirstSimple`

One centred card, `max-width: 560px`, `padding: 72px 32px`, everything centre-aligned:

- A 60px teal rounded-square badge with a teal glow shadow.
- Mono uppercase eyebrow.
- `h1` at 38px.
- One paragraph, `max-width: 460px`.
- A centred wrap of three fact pills, each with a teal icon.
- A pill-shaped primary button.
- An underlined ghost text link beneath it.

---

## Token mapping — design → FLS

The design's own variables and their FLS equivalents. Everything below is a role token that exists in
`themes/default/.../theme.css`, so it works across themes.

| Design var | FLS token / utility | Note |
| --- | --- | --- |
| `--color-primary` | `primary` / `on-primary` | Same role. |
| `--color-secondary` | `secondary` / `on-secondary` | Solid teal badge fills. |
| `--color-secondary-600` | `text-secondary` | **FLS has no numeric colour ramp.** Darker-teal text becomes plain `text-secondary`. |
| `rgba(0,206,201,0.12)` icon tiles | `bg-secondary/10` | Matches the existing `.chip-secondary` contract. |
| `--bg-elev` | `bg-surface` | The elevated panel colour. |
| `--bg` | page background | Owned by the shell, not this page. |
| `--border` | `border-border` | |
| `--fg-1` / `--fg-2` / `--fg-3` | `text-on-surface` / `text-muted` / `text-muted` | FLS has two foreground roles, not four; `--fg-3` and `--fg-4` both collapse to `text-muted`. |
| `--grey-50` / `--grey-100` / `--grey-200` | `bg-surface-2` | FLS has one secondary surface, not a grey ramp. |
| `--color-success-light` + `#22543D` | `bg-success-light text-on-success-light` | The pair already exists. |
| `--color-warning-light` + `#B7791F` | `bg-warning-light text-on-warning-light` | |
| `--font-heading` | `font-display` | |
| `--font-mono` | `font-mono` | |
| `--font-body` | `font-sans` (the default) | |
| radius `10px`/`12px` | `rounded-lg` | |
| radius `14px`/`16px` | `rounded-xl` | Not a theme token — see below. |
| radius `999px` | `rounded-pill` | |

**Radius caveat.** FLS exposes `--fls-radius-sm/md/lg/pill` only, aliased to Tailwind's
`rounded-sm/md/lg/pill`. The design's 14–18px panel radii have no role token. Use `rounded-lg`
(themeable) for anything that should follow the theme, and reserve literal `rounded-xl` for the few
places where the larger radius is load-bearing — `c-card` already sets a literal `rounded-xl`, so
that precedent exists.

**Shadow caveat.** The teal glow under the badges (`0 8px 20px -8px rgba(0,206,201,0.6)`) is a
brand-coloured shadow with no FLS token. `shadow-lg` is the themeable stand-in.

---

## Icons

The design uses Phosphor names that FLS's semantic registry does not carry. FLS resolves
`<c-icon name="..." />` through `freedom_ls/icons/semantic_names.py` plus four per-set maps in
`freedom_ls/icons/mappings.py` (heroicons, lucide, and two more).

| Design icon | Nearest existing FLS semantic name |
| --- | --- |
| `ph-list-numbers`, `ph-list-checks` | `form` |
| `ph-files` | `course_part` |
| `ph-book-open` | `topic` |
| `ph-arrows-counter-clockwise` | `retry` |
| `ph-check-circle`, `ph-check` | `success`, `check` |
| `ph-lightbulb` | `info` |
| `ph-arrow-right` | `next` |
| `ph-arrow-left` | `previous` |
| `ph-hand-waving`, `ph-coffee`, `ph-infinity`, `ph-floppy-disk`, `ph-leaf`, `ph-sparkle` | **none** |

Adding a semantic name means editing `semantic_names.py` and **all four** maps in `mappings.py`.
Prefer an existing name over adding one.

---

## What the design shows that FLS has no data for

`Form` (`freedom_ls/form_engine/models.py:43`) carries `title`, `subtitle`, `rendered_content`,
`strategy`, `quiz_show_incorrect`, `quiz_pass_percentage` and `submit_on_exit`. The start-page view
(`view_form`, `freedom_ls/learner_interface/views.py:912`) adds `question_count`, `page_count`,
`incomplete_form_progress`, `completed_form_progress` (5 latest) and `buttons`.

| Design element | Backed by | Verdict |
| --- | --- | --- |
| Question count | `question_count` | Real. |
| Page count | `page_count` | Real. |
| First-time vs returning framing | `completed_form_progress` being empty | Real. |
| Previous attempts + scores | `completed_form_progress`, `FormProgress.scores` | Real. |
| "Saves as you go" | `Form.submit_on_exit` (inverted) | Real. |
| "Instant feedback" | `Form.quiz_show_incorrect` | Real. |
| "~10 min · Relaxed pace" | nothing — there is no duration field | **Not backed.** |
| "Unlimited tries" | nothing — no attempt-limit field exists | **Not backed** (true today, but unmodelled). |
| "What it covers" tags | `FormPage.category` / `FormQuestion.category` exist but are a scoring input, never surfaced to learners | **Not backed** without new work. |
| "How it works" 3 steps | static copy | Static, not data. |
| "Back to section" / "Review the section first" | no previous-URL in the form start context | **Not backed.** |
| Attempt numbering ("Start attempt 4") | derivable from `completed_form_progress` count, but the count is capped at 5 | **Not backed** reliably. |
| Best score, growth, trend | not computed anywhere | **Not backed.** |

The idea is explicit: *"you must not make new functionality based on the design. The point is to copy
the look and feel."* So every "not backed" row is dropped rather than faked.
