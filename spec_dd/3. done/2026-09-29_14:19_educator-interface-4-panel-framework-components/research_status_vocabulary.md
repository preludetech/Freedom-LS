# Research: status badge vocabulary and FLS role tokens

For `educator-interface-4-panel-framework-components`. Answers the conflict between this idea's
fixed badge vocabulary and spec 10's attention-flag mapping, using the domain glossary, the brand
and frontend-styling skills, and the actual theme CSS.

## 1. Every badge an educator screen needs, grouped by the thing it describes

Two different dimensions get called a "status" across specs 6, 7, 9, 10, and they must not share
one vocabulary or one enum, because they answer different questions ("is this row in force?" vs
"how is this learner doing?"). The domain glossary already warns about this: `is_active` means
"three different things on three models" and a sentence naming two of them must name the model.

### 1a. Administrative state (is this account/cohort/grant in force?)

| Entity | Field | States a badge shows | Word chosen by its spec | Source |
|---|---|---|---|---|
| `Cohort` | `is_active` (new, spec 6) | active / inactive | **"inactive"** — idea 6: "Filters: status (active by default, with a toggle to show inactive)" | `educator-interface-6…/idea.md` |
| `Learner` (org membership) | `is_active` | active / pending / removed | **"removed"**, not "inactive" — idea 7: "List. Name, email, status (active, pending, removed)…" | `educator-interface-7…/idea.md` |
| `LearnerCourseRegistration`, `CohortCourseRegistration` | `is_active` | unregistered/reactivated, described by verb not by a badge word yet | Undecided — idea 6/7 describe the *action* ("unregister"/"re-register") and the *confirmation copy*, never a status noun for the registration row itself | `educator-interface-6…/idea.md`, `-7…/idea.md` |
| Educator role assignment (`ObjectRoleAssignment`/`SystemRoleAssignment`) | `is_active` | active / removed (implied) | Idea 9 only says "deactivates the assignment"; no badge word chosen | `educator-interface-9…/idea.md` |
| `Learner` "pending" | derived (user created by staff, never logged in) | pending | Confirmed by roadmap decision: "A learner is 'pending' when staff created the account and the person has never logged in." | `roadmap.md` §Assumptions, "No invitation model" |

**Naming collision found:** the same underlying flag (`is_active=False`) is called **"inactive"**
on `Cohort` and **"removed"** on `Learner`. This is not a drafting slip — the domain glossary
explicitly sanctions reusing `is_active` as "the house flag name" across models with different
meanings, and the roadmap's own decision 1 is "deactivate, never delete" for both, so the two specs
independently chose the word that reads best for what is being deactivated (a *group* goes
"inactive"; a *person's org membership* is "removed" — because unlike a cohort, "inactive learner"
would misleadingly suggest "hasn't logged in," which is already the word "pending"). **Spec 4
should not force one word onto both** — it should own a per-entity label lookup, keyed on model,
not a single enum shared by cohort and learner badges. Flag the registration-row and
assignment-row words as open — recommend "active" / "inactive" for both (matching Cohort, since
neither is a person-membership row) but note this is not yet settled by 6, 7 or 9 and spec 4 should
ask rather than assume.

### 1b. Progress / attention state (how is this learner doing in a course?)

This is spec 10's territory and is the one the idea 4 vocabulary line ("active, inactive, pending,
complete, in progress, stalled") actually conflicts with. Spec 10's own idea resolves it:

> "The attention flags are the report's: no activity, failed latest quiz, inactive. The status badge
> vocabulary in spec 4 maps to them plus not started, in progress and complete. One definition, in
> `reports`, used by the dashboard, the lists and the badges."

So the settled set (six words, not idea 4's six — two are different) is:

| Word | Meaning | Owner / defined at |
|---|---|---|
| `not started` | `CourseProgress.progress_percentage == 0` | `reports/gather.py:726` computes `not_started_count` this way; `learner_interface`'s existing `CourseListingStatus` uses the learner-facing word "Registered" for the same 0%-progress state — a prior-art label mismatch spec 10 will need to reconcile, not spec 4 |
| `in progress` | `0 < progress_percentage < 100` | Same gather; matches the *already-shipped* learner-facing vocabulary in `learner_interface/utils.py` (`IN_PROGRESS = "in_progress"`, displayed "In progress") and `course_status_eyebrow.html` |
| `complete` | `progress_percentage == 100` | `reports/gather.py:727` `complete_count`; matches the shipped `CourseListingStatus.COMPLETE = "complete"`, displayed **"Completed"** — i.e. the codebase's convention is already **code value "complete", display label "Completed"** (past participle for prose, bare adjective for the identifier). Spec 4 should follow this convention rather than pick between "complete"/"completed" itself — it is already decided elsewhere in the codebase. |
| `no activity` | `AtRiskRule` id `no_activity`, label "No recorded activity" — the learner has no progress row at all | `reports/at_risk.py:56` `NoRecordedActivityRule` |
| `failed latest quiz` | `AtRiskRule` id `failed_latest_quiz` | `reports/at_risk.py:67` `FailedLatestQuizAttemptRule` |
| `inactive` (attention sense) | `AtRiskRule` id `inactive`, label "No activity recently" — no completion in the last N days (default 7), despite having *some* progress | `reports/at_risk.py:89` `InactiveForDaysRule` |

**Second naming collision, and it is the one the conflict brief asked about:** the word
**"inactive"** now has *three* live senses reachable from one screen: a deactivated `Cohort`
(1a), a `Learner` who is neither pending nor active (which idea 7 explicitly calls "removed", not
"inactive" — so this sense doesn't actually occur in the learner list), and an at-risk *attention
flag* meaning "hasn't completed anything in 7 days" (1b, from `InactiveForDaysRule`, whose own rule
id is literally `"inactive"`). Idea 4's own vocabulary line ("active, inactive, pending, complete,
in progress, stalled") reads as if it is one flat enum; it is not — "active"/"pending" belong to
1a (Learner), "inactive" is ambiguous between 1a (Cohort) and 1b (attention flag), and "stalled" is
a coined word matching **nothing** in the codebase (see below). Spec 10's later, more careful
wording — "no activity, failed latest quiz, inactive" — is authoritative over idea 4's list because
idea 4 explicitly says "Spec 10 decides how 'stalled' is computed; this spec only styles it," and
spec 10 then defined the vocabulary without using "stalled" or bare "active" at all. **Idea 4's
list is superseded by idea 10's; "stalled" should be dropped, not implemented.**

## 2. FLS role tokens

Full list, from `freedom_ls/themes/default/static/themes/default/theme.css` (the always-on
baseline; `first_class` overrides only listed where it changes the *value*, not the token set) and
`claude_plugins/fls-dev/resources/frontend_styling.md`.

**There is no dark mode.** Both shipped themes (`default`, `first_class`) are light-only — no
`prefers-color-scheme`, no `.dark` class, no dark token set anywhere in the repo. "Light and dark"
contrast checking asked for in the brief does not apply today; if spec 4 (or a later theme) adds a
dark theme, every ratio below needs redoing against that theme's own values, not derived from these.

| Token pair | Hex (default theme) | Badge-suitable? |
|---|---|---|
| `primary` / `on-primary` | `#2B6CB0` / `#FFFFFF` | Yes — brand blue, not semantic; not for status |
| `secondary` / `on-secondary` | `#475569` / `#FFFFFF` | Yes, as a **neutral** tone |
| `accent` / `on-accent` | `#F59E0B` / `#1A2332` | No — brand guidelines reserve accent for highlights/callouts, not status |
| `success` / `on-success` | `#38A169` / `#FFFFFF` | As a **solid** badge fill, no (see contrast below) — use `success-light` instead |
| `warning` / `on-warning` | `#F6E05E` / `#1A2332` | Yes as solid fill (dark-on-light already) |
| `error` / `on-error` | `#E8553D` / `#FFFFFF` | As a **solid** badge fill, no — use `error-light` |
| `info` / `on-info` | `#0EA5E9` / `#FFFFFF` | As a **solid** badge fill, **no — fails AA outright** |
| `success-light` / `on-success-light` | `#F0FFF4` / `#22543D` | Yes — this is the badge-safe pairing |
| `warning-light` / `on-warning-light` | `#FFFFF0` / `#744210` | Yes |
| `error-light` / `on-error-light` | `#FFF5F5` / `#742A2A` | Yes |
| `info-light` / `on-info-light` | `#EBF8FF` / `#2A4365` | Yes |
| `surface-2` / `muted` | `#F3F4F6` / `#4A5568` | Yes — this is `chip-muted` already, good for "removed"/neutral |
| `surface` / `on-surface` | `#FFFFFF` / `#1A2332` | Not really a "tone," it's the page background |

### Computed WCAG contrast ratios (light theme only — no dark theme exists)

Using the standard relative-luminance formula against the hexes above:

| Pair | Ratio | AA normal text (4.5:1) | AA large text / UI (3:1) |
|---|---|---|---|
| `on-surface` (#1A2332) on `surface` (#FFFFFF) | 15.7:1 | Pass | Pass |
| `muted` (#4A5568) on `surface-2` (#F3F4F6) | ~6.8:1 (matches brand-guidelines' quoted figure) | Pass | Pass |
| `on-success` (white) on `success` (#38A169) — **solid fill** | **~3.25:1** | **Fail** | Pass (barely) |
| `on-error` (white) on `error` (#E8553D) — **solid fill** | **~3.62:1** | **Fail** | Pass (barely) |
| `on-info` (white) on `info` (#0EA5E9) — **solid fill** | **~2.77:1** | **Fail** | **Fail** |
| `on-warning` (midnight) on `warning` (#F6E05E) — solid fill | ~11.8:1 | Pass | Pass |
| `on-secondary` (white) on `secondary` (#475569) — solid fill | ~7.6:1 | Pass | Pass |
| `on-success-light` on `success-light` | ~8.45:1 | Pass | Pass |
| (the other three `*-light` pairs are the brand's own pre-tested combinations, same shape) | ≥7:1 typical | Pass | Pass |

**Finding:** a badge styled as a *solid* success/error/info fill with the matching `on-*` white
text fails AA for normal-size badge text (info fails even the large-text/UI threshold outright).
This is exactly why the existing `c-chip` component (`freedom_ls/base/templates/cotton/chip.html`,
classes in `tailwind.components.css:227-261`) never does this: `.chip-success` is
`bg-success/15 text-success` (colour-as-text on a tint, not colour-as-fill with white text), and
`.chip-warning` is `bg-warning/30 text-on-warning` (dark text, which is safe). **Spec 4's status
badge should follow the same shape `c-chip` already uses — tint background, saturated or `on-*`
text — never a solid fill with `on-success`/`on-error`/`on-info` white text at chip/badge sizes.**

## 3. Fixed vocabulary vs. tone + mapping owned elsewhere

**Recommendation: a small fixed set of tones (neutral / info / success / warning / danger), picked
by the caller, with the domain-status→tone mapping owned by whichever spec owns the status.**

Reasons, weighed against "the badge has its own fixed domain vocabulary":

- **Two owners already exist for the words**, and they are not spec 4. Spec 10's idea says outright
  "One definition, in `reports`, used by the dashboard, the lists and the badges" — the *status
  words* for progress/attention live in `reports/at_risk.py` and `reports/report_data.py` (already
  shipped, already carrying a `severity` field: `SEVERITY_ERROR` / `SEVERITY_WARNING`, "a role token
  name, so a badge is coloured by the theme rather than by this module" — `at_risk.py:50-53`). The
  administrative words (active/inactive/pending/removed) live in specs 6, 7 and 9's own list/detail
  views. If spec 4 hard-codes the six-word list from its own idea, it either duplicates a mapping
  spec 10 already half-built (`severity` → tone) or drifts from it the day spec 10 lands.
- **The precedent in the repo already does it this way.** `AtRiskRule.severity` is deliberately "a
  role token name, so a badge is coloured by the theme rather than by this module" — i.e. the rule
  that *knows* the domain status also names the tone, and the badge component just renders
  `<c-chip variant="{{ flag.severity }}">`. A fixed vocabulary inside `panel_framework` would
  reintroduce exactly the coupling that comment is written to avoid.
- **A fixed vocabulary badge can't serve both dimensions without a bigger enum than either spec
  wants.** Section 1 above shows six-plus distinct words already, across two unrelated dimensions
  (administrative state vs. progress/attention), each owned by a different spec, each likely to
  grow (spec 8's bulk import will add its own per-row outcome labels; spec 11's audit log will want
  its own action labels). A tone set of five is stable; a hardcoded status list is not.
- **Cons of the tone approach**, to be honest about them: it pushes a little more work onto each
  caller (6, 7, 9, 10 each need one line mapping their own word to a tone), and it means the status
  *text* the badge prints is just whatever string the caller passes — so accessibility ("badges
  carry text, not just colour," per idea 4's own settled rule) is only as good as the caller's
  copy, not enforced by the component. Spec 4 should still fix the *tone names* and their
  token/contrast pairing (that part is genuinely fixed vocabulary — "success," "warning," "danger,"
  "info," "neutral" are not going to grow), just not the *domain words* that pick a tone.

Concretely: `<c-panel-status-badge tone="success|warning|danger|info|neutral">{{ label }}</c-panel-status-badge>`,
where `tone` reuses the same five names `c-chip`'s `variant` already uses (`success`, `warning`,
`error`→rename or alias to `danger` for badge semantics, `info`, `muted`→`neutral`), and each
caller (6, 7, 9, 10) supplies both the tone and the exact label text from section 1. Spec 10's
`AtRiskRule.severity` values (`"error"`, `"warning"`) already match `c-chip`'s variant names, so no
translation layer is needed there — just render `variant="{{ flag.severity }}"`.

## 4. Proposed mapping table

| Status word | Dimension | Tone | Token pair | Brand-guidelines objection? |
|---|---|---|---|---|
| active (Cohort) | 1a | neutral or success | `chip-muted` (`surface-2`/`muted`) or `chip-success` tint | None — plain "in force" state, arguably doesn't need a warm colour at all; recommend neutral so "active" doesn't visually compete with "complete" |
| inactive (Cohort) | 1a | neutral | `chip-muted` | None |
| pending (Learner) | 1a | neutral or info | `chip-muted` or `chip-info` tint | None — "pending" is a wait-state, `info` tint reads better than `muted` if screens need it to stand out from "active" |
| active (Learner) | 1a | success or neutral | tint | None |
| removed (Learner) | 1a | neutral | `chip-muted` | None — never `error`/danger: "removed" here means "no longer in the organisation," not a fault. Brand voice ("never blame") argues against a red/danger badge for a routine, reversible admin action |
| not started | 1b | neutral | `chip-muted` | None |
| in progress | 1b | info | `chip-info` tint | None — matches `learner_interface`'s existing "in progress" blue-ish reinforcement icon in spirit |
| complete | 1b | success | `chip-success` tint | None — "positive states, completion" is literally `success`'s documented role |
| no activity (attention) | 1b | danger (`error`) | `chip-error` tint | None — `AtRiskRule` already sets `SEVERITY_ERROR` |
| failed latest quiz (attention) | 1b | danger (`error`) | `chip-error` tint | None — already `SEVERITY_ERROR` |
| inactive (attention, 7-day) | 1b | warning | `chip-warning` (`bg-warning/30 text-on-warning`) | None — already `SEVERITY_WARNING`; note `warning`'s own guardrail: "Never for text" as a plain fill — the existing `.chip-warning` class already respects this (dark text on tint, not white-on-solid) |
| stalled | — | — | — | **Drop.** Not defined by spec 10, collides with "inactive" (attention), and coining it would leave two words for one concept, which the domain vocabulary skill calls worse than reusing a taken word |

Nothing here contradicts `brand-guidelines`: the guardrail that actually bites is "never use Sand
[warning] or Forest [success] as text colours on light backgrounds," which the `-light`/tint chip
classes already respect, and "never blame" in copy, which is why "removed" and "inactive" are
mapped to `neutral`, not `danger`, despite both meaning "not active."

status: ok
