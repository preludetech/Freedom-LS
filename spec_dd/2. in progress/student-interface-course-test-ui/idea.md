# Student interface — course test/exam UI

We need the student interface for showing exams (FLS "Forms") to look good and on spec.

Follow the designs at `/home/sheena/workspace/lms/design/computed/exam` (with `desktop/`, `tablet/`, `mobile/` variants). These designs match the **first-class** theme. Build so **everything works for the default theme first**, then layer first-class customisations. Everything must be **easy to theme, style and change**.

The designs were made by a third-party tool that is not aware of our code or models. **The goal is to copy the design, not to implement all the things.** Do not implement new features (or new data) without checking first — several design elements have no backing in our models and are explicitly out of scope (see below).

This is purely the **student-facing presentation** of the existing Form/test flow. It re-skins and restructures the current screens; it does **not** add new scoring strategies, question types, or model fields.

## What already exists (reuse it)

- **Models:** `Form` (strategies `QUIZ` and `CATEGORY_VALUE_SUM`, with `quiz_pass_percentage` / `quiz_show_incorrect`), `FormPage` (ordered), `FormQuestion` (4 types — `multiple_choice`, `checkboxes`, `short_text`, `long_text`), `QuestionOption` (`text`, `value`, `correct`).
- **Progress:** `FormProgress` (one per attempt, supports a full history of attempts per user+form; `start_time` / `completed_time` / `scores`), `QuestionAnswer` (one per question per attempt). Methods: `save_answers`, `complete`, `score`, `quiz_percentage`, `passed`, `get_incorrect_quiz_answers`, `get_current_page_number`.
- **Current views/flow:** `form_start` → `form_fill_page` (full-page POST → `save_answers` → redirect; answers persist on page advance) → `course_form_complete`. Templates `course_form*.html` already use cotton components.
- **Theming:** Tailwind v4 `@theme` tokens with a `default` and a `first_class` theme. Icons render as inline SVG via `c-icon` (Heroicons by default; a Phosphor mapping also exists). See `research_theming_and_components.md` for the full token + component + icon mapping.

## Scope decisions (confirmed)

**In scope** — re-skin/restructure these three screens to match the design:

- **Test start screen**
- **Test questions page (the "runner")**
- **Results page**

**Out of scope for this spec (do not build; leave any related TODO/comments intact):**

- **History page** + trend chart (design includes it; deferred to a future spec, alongside retry limits). On the start screen we still show a lightweight "previous attempts" summary, but **omit the "View all" link entirely** — no stubs or disabled placeholders. If a feature isn't implemented, the learner should not see a control for it.
- **Unbacked design features — omit entirely:** per-question "Flag for review", per-question "Here's the idea" explanations, any timer / countdown / "relaxed pace" pill, estimated completion time (e.g. "~10 min"), and the per-topic results breakdown ("How you did by topic"). These have no model backing and are not part of this work.
- **No new question types.** Demonstrate only the four existing field types in demo content, using standard widgets in standard ways. Do **not** special-case True/False — a two-option `multiple_choice` renders like any other multiple-choice question (no bespoke True/False styling).

# Pages

## Test start screen

- Re-skin the existing form overview to match the design: title, subtitle/eyebrow, intro/markdown content, and a meta grid showing only **truthful, derivable** facts (e.g. number of questions, number of pages). Drop the estimated-time and "unlimited tries" cells unless they map to real data.
- Show a compact **previous attempts** summary from `FormProgress` history (best/most-recent scores where applicable). Omit the design's "View all" link — the history page is deferred, so no link/placeholder is shown.
- A clear **Start / Continue / Try again** call to action (reuse existing button logic).
- Uses the normal app chrome (global header; no course sidebar needed here).

## Test questions page (the "runner")

- Displays **one `FormPage`'s questions** at a time.
- **Its own full-screen interface** — do **not** render the course-player sidebar/TOC or the standard course chrome. Once the learner is inside the test, the runner owns the viewport (own top bar, progress strip, footer nav). This needs a dedicated sidebar-less base layout; the start and results screens keep normal chrome. See `research_theming_and_components.md` §4.
- **Progress bar** at the top (page X of Y; derived server-side).
- Render all four existing question types. Choices must be **real, accessible form controls** — native `<input>` wrapped in styled `<label>` tiles (not click-handler divs), grouped in `<fieldset>`/`<legend>`. See `research_runner_interactions.md` §5.
- **Navigation:** keep the current full-page POST→save→redirect ("PRG") pattern. **Next** saves the current page then advances; **Previous** is a plain GET link (does not save in-progress edits) and re-populates from saved answers. Page dots reflect accessible/visited pages.
- An honest **answered count** (e.g. "5 of 8 answered") reflecting persisted answers — no misleading "saved" claim while a page is mid-edit. **No live per-keystroke autosave** — the count reflects answers persisted on page advance (PRG). This is the confirmed, simplest approach.

On the **final page**, clicking Next opens a **review-or-submit dialog**:

- Title along the lines of "Ready to submit?"; explains that submitting scores the attempt and answers can't be changed afterwards.
- Shows only truthful counts (answered / unanswered — **no** "flagged").
- **Go back and review** (dismiss, stay) vs **Submit** (POST → `complete()` → results). Submit button disables on click to prevent double-submit.

## Results page

- After submit, redirect here.
- If the test has **automated marking** (e.g. `QUIZ` strategy), show the marks — score, pass/fail state, and (where `quiz_show_incorrect` is set) the "worth another look" review of incorrect answers using `get_incorrect_quiz_answers`. Match the design's banner / score-ring / stats treatment, but only with data we actually have.
- Otherwise (no automated score available), clearly say **marking is in progress**.
- Allow the learner to **navigate back to the course player** (and retry where appropriate).
- Drop the per-topic breakdown and per-question explanations (out of scope).

# Navigation & exit behaviour

A learner can launch a form, move back and forth between pages, fill in answers, and retry — reusing the existing flow.

- **Exit behaviour is configurable** via an **optional `Form` field**. Mid-test exit supports two modes (some tests should finalise on exit; others should let the learner pick up where they left off):
  - **Save on exit (default)** — leaving keeps an **incomplete** `FormProgress`; the learner continues from where they stopped on their next visit (this is the existing model behaviour via `get_or_create_incomplete` / `get_current_page_number`, surfaced as the start screen's "Continue" CTA). The confirmation dialog warns that progress is saved and they can resume.
  - **Submit on exit** — leaving the runner mid-test **finalises and scores** the attempt. The confirmation dialog warns that leaving will submit their answers.
- In both modes:
  - Intercept the in-runner exit control (the "X") with an Alpine confirmation dialog → on confirm, take the mode-appropriate action (submit→complete→results, or just leave and return to the course player).
  - Use `beforeunload` as a best-effort courtesy warning for raw browser navigation, understanding its real limits (generic text only; unreliable on mobile; doesn't fire for in-app swaps). See `research_runner_interactions.md` §2.
  - For **submit-on-exit**, the **reliable safety net** is server-side: when a learner with an incomplete `FormProgress` next returns, complete the stale attempt before starting a new one. Add an idempotency guard so `complete()` is not applied twice. (In **resume** mode the incomplete attempt is simply reopened.)

# Theming & accessibility (cross-cutting)

- **No hardcoded hex/fonts/radii in templates.** Every colour/font/radius flows through `@theme` tokens / Tailwind utilities so a theme override needs zero template changes. Map the design's first-class palette to FLS tokens per `research_theming_and_components.md` §1 & §5. Do not add Phosphor CSS font links — icons go through `c-icon`.
- Reuse existing cotton components where they fit (`c-button`, `c-button-group`, `c-icon`, `c-chip`, `c-modal`, `c-page`, `.surface`, markdown container); add small new partials for the meta grid, score ring (SVG via `currentColor`), runner bar, progress strip, page dots, and results stats. See §2.
- Accessibility baseline: real inputs + labels + fieldset/legend; focus management and an `sr-only` progress announcement on page change; dialogs with `role="dialog"`, `aria-modal`, focus trap, Escape, and focus return (or a native `<dialog>`).

# Research

- `research_theming_and_components.md` — design→FLS token mapping, cotton component reuse map, icon strategy, runner layout integration, easy-to-theme authoring rules.
- `research_runner_interactions.md` — navigation mechanics, submit-on-exit + final-page dialogs, autosave honesty, accessibility patterns, common multi-page-test pitfalls (with cited sources).
