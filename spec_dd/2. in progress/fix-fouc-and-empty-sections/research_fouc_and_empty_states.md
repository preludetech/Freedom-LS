# Research: FOUC prevention & empty-state UX

Two related research questions for the Learner Experience Polish work. Part A is the
"flash of unstyled content" problem in our Alpine-driven components (concretely: the
`c-picture` zoom modal that briefly appears open on page load). Part B is the design
question of what to show when a list is empty.

---

## Part A — Preventing FOUC for Alpine.js components

### What's actually happening

Alpine.js loads with `defer` (see `freedom_ls/base/templates/_base.html`). That means:

1. The browser parses HTML and renders the page using whatever inline styles / classes exist.
2. Alpine boots after the document is parsed and starts walking the tree, evaluating
   `x-data`, `x-show`, `x-bind`, etc., and toggling `display` on elements.
3. Until step 3 happens, anything controlled only by `x-show` is **rendered with its
   natural CSS** — i.e. visible. This is the "flash before Alpine boots" window.

For `c-picture` (`freedom_ls/content_engine/templates/cotton/picture.html`):

```html
<div x-show="open"
     x-cloak
     class="fixed inset-0 flex justify-center items-center z-50 backdrop-blur-lg">
```

The intent: hide until `open` becomes truthy. The reality on first paint: `display:flex`
+ `fixed inset-0` + `z-50` = a fullscreen modal sitting on top of the page until Alpine
runs. The author *did* add `x-cloak`, but the file wasn't grepping up any matching
`[x-cloak] { display: none !important }` rule in `tailwind.input.css`,
`tailwind.components.css`, or `_base.html`. **That CSS rule is required** — without it,
`x-cloak` is just an inert attribute. This is the single most common FOUC cause in
Alpine codebases and is almost certainly the root cause of the `c-picture` flash.

### Reference: https://alpinejs.dev/directives/cloak

> `x-cloak` attributes will be removed from elements when Alpine initializes. This is
> useful for hiding pre-initialized DOM. It's typical to set the following global
> styles for this to work: `[x-cloak] { display: none !important; }`.

### How `x-cloak` works

`x-cloak` is a marker attribute. Alpine doesn't apply any styling to it itself — that's
your job. The lifecycle:

1. HTML lands in the DOM with `x-cloak` set on the element.
2. Your global CSS rule `[x-cloak] { display: none !important; }` matches → element
   is hidden by the browser immediately, no JS required.
3. Alpine boots, walks the tree, evaluates `x-show`, and removes the `x-cloak`
   attribute from every element it processes.
4. The CSS selector no longer matches → the browser reveals the element if `x-show`
   evaluates truthy, or `x-show` keeps it hidden via `display: none`.

The order is important: `x-cloak` is removed *after* Alpine has set the correct
`display` for `x-show`. So there's no second flash.

### Where the CSS rule should live

For this project the right home is `tailwind.input.css` (or `tailwind.components.css`),
inside an `@layer` so it isn't purged and it has predictable specificity:

```css
@layer base {
  [x-cloak] { display: none !important; }
}
```

Putting it in a `<style>` tag in `_base.html` also works but splits the concern;
keeping it next to other base layer rules is better. After adding it, run
`npm run tailwind_build`.

### `display: none` vs `hidden` attribute vs `x-show` initial state vs `x-cloak`

Four overlapping mechanisms; they aren't interchangeable.

| Mechanism | When it hides | Survives Alpine boot? | Notes |
|---|---|---|---|
| `class="hidden"` (Tailwind `display:none`) | Immediately, from CSS | Alpine doesn't remove it | Use for genuinely server-hidden elements not driven by `x-show` |
| `hidden` HTML attribute | Immediately, browser default | Alpine doesn't touch it | Same effect as `display:none` but lower specificity — Tailwind's `block`/`flex` will override it |
| `x-show="open"` with `open: false` | Only after Alpine runs | n/a | Causes FOUC unless paired with `x-cloak` |
| `x-cloak` + the CSS rule | Immediately, from CSS | Yes — Alpine removes the attribute | Designed exactly for this case |

**Rule of thumb:** if the element's visibility is controlled by Alpine state, add
`x-cloak`. If it's never controlled by Alpine, don't bother — use Tailwind classes.

`x-show` vs `x-if`: `x-show` toggles `display:none` on an element that's already in the
DOM. `x-if` adds/removes the element entirely. For a modal that's closed by default,
`x-if` avoids FOUC even without `x-cloak` because the markup isn't in the DOM at all
on first paint. The trade-off: `x-if` re-creates the element on every open, which loses
form state, and it requires a `<template>` wrapper. For the `c-picture` modal, `x-cloak`
+ the global rule is the cleaner fix.

### "Closed by default" markup beats client-side init

The most robust pattern is: render the closed state on the server, and only let Alpine
*open* things. Concretely for `c-picture`:

- The thumbnail is always visible — fine, no Alpine needed for that.
- The modal overlay should be *server-rendered as hidden*. Two ways:
  1. Add `x-cloak` plus the global CSS rule (recommended — minimal change).
  2. Wrap in `<template x-if="open">…</template>` so it isn't in the DOM at all
     until opened.

This principle generalises. Anything that's "open/expanded/visible only after a user
action" should be hidden at HTML parse time, not after Alpine wakes up. Server-rendered
initial state means the page is correct even with JS disabled or slow.

### HTMX equivalents

HTMX's FOUC story is different because HTMX doesn't hide things — it swaps content.
The relevant primitives:

- **`htmx-indicator`** — built-in class for loading indicators. HTMX adds the
  `htmx-request` class to the triggering element during a request, and `htmx-indicator`
  elements are styled to be hidden by default and shown when `htmx-request` is on an
  ancestor. The default rule HTMX ships is:

  ```css
  .htmx-indicator { opacity: 0; transition: opacity 200ms ease-in; }
  .htmx-request .htmx-indicator { opacity: 1; }
  .htmx-request.htmx-indicator { opacity: 1; }
  ```

  Reference: https://htmx.org/docs/#indicators

- **`hx-swap-oob`** — out-of-band swaps. The server can return multiple fragments
  in one response and HTMX will splice each into its target by id. Useful for
  "update header badge and the main panel from a single response," not directly a
  FOUC tool, but it lets you avoid intermediate empty states by sending the final
  state in one response.

- **`hx-preserve`** — keeps an element's state across swaps. Relevant for FOUC because
  it stops in-flight Alpine state from being clobbered.

- **`htmx:load` event** — fires after HTMX swaps content in. If you have Alpine
  components inside swapped HTML, Alpine 3 auto-initialises new nodes via a
  `MutationObserver`, so usually you don't need to do anything. But the same FOUC
  rules apply: any `x-show` inside swapped HTML must be paired with `x-cloak`.

There is no HTMX equivalent to `x-cloak` because HTMX doesn't have an initialisation
phase that mutates already-rendered DOM. The HTML you send is what gets rendered.

### How HeadlessUI / other libraries handle it

- **HeadlessUI (React/Vue)** — components render `null` (React) or use `<Transition>`
  with `enter-from-class` / `leave-to-class` so the closed state is "not in the DOM"
  rather than "in the DOM but display:none". No FOUC because there's nothing to flash.
- **Radix UI** — same approach: portal-based components (Dialog, Popover) only mount
  when `open=true`. The `Presence` primitive handles unmount animations.
- **Alpine UI** (the official component library) — uses `x-show` + `x-cloak`
  consistently and expects the global CSS rule. See
  https://alpinejs.dev/component for examples; every modal/dropdown example in the
  Alpine docs starts with a note about adding the cloak CSS.
- **Bootstrap 5** — modals are hidden via `display:none` on `.modal` by default in the
  stylesheet, then JS toggles `.show`. Server-side initial state by design.

The shared lesson: the closed state must be enforceable from CSS alone, before any JS
runs.

### Common pitfalls

1. **Forgetting the global `[x-cloak]` rule.** This is the single biggest one. The
   attribute is on the element but does nothing. Symptom: things flash open on every
   page load, then snap closed.
2. **Using `x-show` without `x-cloak`.** Even with the global rule, you have to
   actually put `x-cloak` on the element. Forgetting it is silent.
3. **Putting `x-cloak` on the wrong element.** It needs to be on the same element as
   `x-show`, not on the `x-data` parent. The CSS selector matches the element
   carrying the attribute.
4. **`x-cloak` inside an `x-data` that itself flashes.** If a parent is visible by
   default and only Alpine hides it, you need `x-cloak` on the parent too. Walk up
   the tree until you hit something that's hidden by static CSS or that should be
   visible.
5. **Tailwind purging the `[x-cloak]` selector.** Attribute selectors with no class
   reference can be purged depending on the safelist. Putting it in
   `@layer base` inside `tailwind.input.css` (or as a raw CSS file imported by it)
   keeps it. Verify it lands in `static/vendor/tailwind.output.css` after building.
6. **Loading Alpine without `defer` *and* before the body content.** Alpine then
   evaluates against an incomplete DOM. Always `defer` Alpine; this project does.
7. **Animations / `x-transition` on a cloaked element.** `x-cloak` plus
   `x-transition:enter` can cause the enter animation to play on first paint when
   the state is `true`. Fix: either start with state `false` and toggle to `true`
   on `x-init`, or use `x-transition.opacity.duration.0ms` for the initial render.
8. **Components inside swapped HTMX content.** If the swapped fragment includes
   `x-show` elements, they need `x-cloak` too — there's a brief moment between
   the swap and Alpine re-initialising the subtree.
9. **CSP build of Alpine.** This project loads `@alpinejs/csp`. The CSP build
   doesn't allow inline expressions in attributes that resolve via `Function()` —
   this is unrelated to FOUC but worth knowing because the fix patterns
   (using component objects in `alpine-components.js`) are already what we do.

### Concrete fix for `c-picture`

1. Add to `tailwind.input.css` (or a dedicated base CSS file imported from it):
   ```css
   @layer base {
     [x-cloak] { display: none !important; }
   }
   ```
2. Run `npm run tailwind_build`.
3. Audit other templates that use `x-show` without `x-cloak`. Quick grep:
   `rg "x-show" --type=html -g '!**/.venv/**'` and cross-check against `x-cloak`.
   Found uses in `_base_interface.html`, `course_minimal_toc.html`,
   `panel_framework/partials/sidebar_nav.html`, `cotton/modal.html`, and
   `cotton/picture.html` already have `x-cloak`; any others should be fixed.
4. Optional: for the modal-style components, consider migrating to
   `<template x-if="open">…</template>` so the modal markup isn't even in the DOM
   when closed. Cleaner accessibility (no orphan `<dialog>`-like element), no
   risk of focus traps catching invisible content.

### References

- Alpine.js `x-cloak`: https://alpinejs.dev/directives/cloak
- Alpine.js `x-show` vs `x-if`: https://alpinejs.dev/directives/show, https://alpinejs.dev/directives/if
- HTMX indicators: https://htmx.org/docs/#indicators
- HTMX out-of-band swaps: https://htmx.org/attributes/hx-swap-oob/
- HeadlessUI Transition / mounting: https://headlessui.com/react/transition
- Radix UI Dialog (mount semantics): https://www.radix-ui.com/primitives/docs/components/dialog
- "FOUC" (MDN-adjacent background): https://en.wikipedia.org/wiki/Flash_of_unstyled_content

---

## Part B — Empty-state UX

The question: when a list (recommended courses, learning history, notifications, etc.)
has zero items, do we hide the section entirely, show a placeholder/CTA, or show a
subtle "nothing here yet" message?

Short answer: **it depends on whether the empty state is *signal* or *noise*.**

### Three options, three contexts

1. **Hide the section entirely** — the section's existence carries no information for
   the user when empty.
2. **Show a placeholder / CTA** — the section's emptiness is itself useful info, and
   there's a meaningful action the user can take to fill it.
3. **Show a subtle "nothing here yet" line** — the section is part of the page's
   structure (heading already shown, sidebar nav links here, etc.) and removing it
   would be more confusing than leaving it.

### When hiding entirely is right

- The section is a *recommendation* or *suggestion* with no fixed slot. "People you
  may know," "trending courses," "based on your activity" — if there's nothing to
  recommend, the absence of recommendations is not a finding the user needs to
  contemplate. Hide it.
- The page has many sections and signal-to-noise matters. Dashboards lose their
  utility fast when half the cards say "no data." Linear and GitHub project boards
  hide empty groupings by default.
- The user is not the cause of the emptiness and can't act on it. If recommendations
  are computed server-side and no items match, there is no useful CTA — telling the
  user "we have no recommendations for you" is a small dignity loss with no upside.

### When a placeholder / CTA is better

- **Onboarding.** A brand-new user with no enrolments is the textbook case: the
  empty list *is* the most important signal the page has. "You haven't enrolled in
  any courses yet — browse the catalogue →" beats a blank screen and beats hiding.
- **Sections the user owns.** "My notes," "My bookmarks," "My drafts" — these are
  user-created collections. Hiding them implies the feature doesn't exist; showing
  an empty state with an example or CTA teaches the feature.
- **The empty state implies future content.** "No new notifications" is fine and
  expected. "No assignments due this week" is reassuring information, not a void.
- **There's a meaningful primary action.** If the right next step is one click
  away ("Enrol in your first course," "Invite a colleague"), an empty-state card
  with that action is much higher-value than hiding.

A strong placeholder has: an illustration or icon, a one-line headline, a short
explanation, and one primary CTA. Two CTAs is the maximum. No CTA at all is fine
when the state is steady-state expected ("inbox zero").

### When a subtle one-liner is enough

- The section is part of the page's information architecture and the heading is
  already visible regardless. Removing the heading would shift layout and confuse
  returning users.
- The empty state is transient and routinely recovered ("no search results" — the
  user will refine their query).
- The empty state is part of a multi-column layout where hiding would create
  awkward whitespace.

A muted "Nothing here yet" or "No results" with no CTA is the right tone for these.
Don't add an illustration; don't add a long explanation; do add a small icon if it
fits the visual rhythm of the rest of the page.

### First-run vs steady-state

These are different problems and deserve different treatments:

| State | Example | Right pattern |
|---|---|---|
| First-run, never had data | New user, zero enrolments | Big placeholder with onboarding CTA |
| First-run for this section, has data elsewhere | New user just enrolled, no progress yet | Subtle "you haven't completed any topics yet" line, or hide |
| Steady-state, expected emptiness | "No assignments due this week" | Subtle one-liner, often positive in tone |
| Steady-state, *unexpected* emptiness | History was cleared, recommendations stale | Subtle one-liner; do *not* re-onboard a returning user |
| Filter / search produced no results | "No courses match 'foo'" | Subtle "no results" with a "Clear filters" CTA |

The mistake to avoid: showing the "Welcome! Enrol in your first course →" onboarding
card to a user who has 47 completed courses but cleared their recent history.
Personalise empty states by what the user has done elsewhere, not just by the count
in this list. A lightweight signal is "has this user ever had data here?" — if yes,
prefer the subtle treatment.

### Accessibility implications

- **Don't render an empty `<section>` with a heading and nothing under it.** Screen
  readers will announce the heading and then drop the user into nothing, which is
  disorienting. Either hide the entire `<section>` (preferred — including its
  heading) or render the empty-state content inside it.
- **If you hide via `display:none` or the `hidden` attribute, the heading is removed
  from the accessibility tree** — good. Don't use `visibility:hidden` (still takes
  layout space and varies by AT) or `aria-hidden="true"` on a visually-present
  element (creates a mismatch).
- **Don't use `role="status"` or `aria-live` for empty states by default.** Live
  regions are for *changes*. An empty state on initial render shouldn't be announced;
  an empty state that appears *after* a filter change can use `aria-live="polite"`
  on the results container so AT users hear "no results."
- **Empty-state CTAs should be real buttons or links**, not divs with click handlers,
  and should have text that makes sense out of context ("Browse courses," not
  "Click here").
- **Illustrations should have empty `alt=""` or be marked `aria-hidden="true"`** —
  they're decorative; the headline carries the meaning.
- **Heading levels should still nest correctly** when sections are hidden. Don't
  leave an `<h2>` in the DOM if its parent section is hidden — it'll mess with the
  outline algorithm in some AT.

### Reference patterns

- **GitHub** — empty repo: large illustration, a list of "Quick setup" actions,
  CLI snippets. Empty issues tab: short message + CTA. Empty notifications:
  illustrated zero-state with a friendly line ("All caught up!"). They distinguish
  "you have nothing" from "this view is filtered to nothing."
- **Linear** — empty boards hide empty status columns by default. Empty inbox is
  illustrated and celebratory ("Inbox zero"). Empty filtered view shows
  "No issues match these filters" with a "Clear filters" link.
- **Notion** — empty pages show contextual CTAs ("Type / for commands"). Empty
  databases show a templated example row that's clearly a placeholder. Heavy
  emphasis on teaching the feature on first encounter.
- **Stripe Dashboard** — most empty states are large illustrated cards on
  first-run, then collapse to subtle "No data" text in steady state. They explicitly
  detect "user has never had data here" vs "user had data and now doesn't."
- **Slack** — empty DMs and channels show onboarding-style states with
  example messages. Empty search results show "No results for 'X'" + suggestions.

### Reading list

- Refactoring UI, "Empty States" chapter (book; physical/eBook only):
  https://www.refactoringui.com/book — the canonical practical reference. Key points:
  show example data when possible, design for first-run separately from steady-state,
  empty states are an opportunity to teach.
- NN/g, "Empty State UX": https://www.nngroup.com/articles/empty-state-interface/
  — research-backed guidance on when illustrations help vs distract, and on the
  difference between user-empty and system-empty states.
- NN/g, "User-empty States: When and How to Use Them":
  https://www.nngroup.com/articles/user-empty-states/
- "Designing Better Empty States" (Smashing):
  https://www.smashingmagazine.com/2024/05/empty-states-better-experience/
- Material Design empty states:
  https://m3.material.io/components/empty-states/overview
- Apple HIG (no dedicated empty-states page; nearest is "Onboarding"):
  https://developer.apple.com/design/human-interface-guidelines/onboarding

### Recommendation for FLS learner experience

For the dashboard sections we're polishing:

- **Recommended courses, no recommendations:** hide the section entirely. The user
  can't act on "we have no recommendations" and the dashboard is denser without it.
- **Learning history, brand-new user:** show a placeholder card — "Start your first
  course to see your progress here" with a "Browse courses" CTA. This is the
  highest-leverage moment to onboard.
- **Learning history, returning user with cleared history:** subtle one-liner —
  "Nothing in your recent history." No CTA; do not re-onboard.
- **Search / filter empty results:** subtle "No courses match these filters" with a
  "Clear filters" link inside the results region, with `aria-live="polite"` on the
  region so AT users are told when the result set changes.
- **Cohorts / classmates lists, none assigned:** hide. The presence of the section
  implies a relationship that doesn't exist for this user; showing it empty is
  confusing.

To distinguish first-run from steady-state we need a "has this user ever had X"
signal. For courses, "has any registration ever existed for this user" is the right
predicate — much better than "current count == 0." The `student_management` app
already tracks registrations; an annotation on the dashboard view is enough.

### Pitfalls / anti-patterns

- **Showing the same empty state to first-run and returning users.** Patronising for
  the latter, unhelpful for the former.
- **Three CTAs in an empty state.** Pick one primary action.
- **Empty states that lie.** "We're working on personalising your recommendations!"
  when nothing is being computed. Users see through it.
- **Inconsistent tone.** Half the empty states are illustrated and friendly; half
  are bare text. Pick a level and apply it consistently — usually: illustrated for
  first-run / page-level empties, plain text for inline / section-level.
- **Spinners as empty states.** A spinner is "loading," not "empty." If the data
  has loaded and is empty, say so.

---

## Summary

**Part A:** the `c-picture` flash is almost certainly because the project doesn't
have the global `[x-cloak] { display: none !important; }` CSS rule. Add it to
`tailwind.input.css` inside `@layer base`, rebuild Tailwind, and audit other
`x-show` uses to confirm they all carry `x-cloak`.

**Part B:** distinguish first-run from steady-state, and tailor each section based
on whether the empty state itself is signal or noise. Hide recommendations when
empty; show an onboarding card for first-run learning history; show a subtle line
for returning users; never render an empty `<section>` with just a heading.
