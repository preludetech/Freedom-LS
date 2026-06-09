# Possible future course-access backends — student UX sketches

These are concrete deployments FLS might grow into. Each is a future `CourseAccessBackend`
(a class selected by the `COURSE_ACCESS_BACKEND` setting). Each one contributes the same things to
the student interface: a **CTA** (flat `cta_label` + `cta_url`), two enforcement booleans
(`can_self_register`, `can_access_content`), optional `filter_visible()`, and optional dashboard
panels (`get_dashboard_contributions()`). Nothing here adds a new core surface.

The purpose of this file is to **pressure-test that seam** against real student journeys — so each
sketch focuses on the buttons and decisions the learner faces, and ends with what it would ask of
the access contract. Button labels are illustrative, not final copy.

### Reference points (already defined)

- **Free** — *today's behaviour.* CTA "Start" → one click → registered → content opens. The only
  decision is "begin or not." `can_self_register=True`.
- **Application-gated** — *being built now.* CTA "Apply now" → a confirmation page ("Apply to X?")
  → the application lands in review; the learner waits, sees status on their dashboard, and
  responds if a reviewer requests changes. Content stays locked until an educator enrols them after
  approval. `can_self_register=False`, `can_access_content=False`.

Everything below is a *future* backend, measured against those two.

---

## 1. Buy a single course

*What it is:* pay once, own one course outright.

**Student sees & does:** on a course they don't own, the CTA shows a **price** —
"Buy · $49" instead of "Start". Clicking opens checkout (a hosted payment page or an off-platform
link). On a successful payment they're returned to the course and **content is open immediately** —
no waiting, no educator step. A course they already own shows "Continue". The decision is purely
commercial: is this course worth the price.

**Educator:** sets the price when authoring/loading the course; no per-learner action.

**Asks of the seam:** the CTA needs to carry a **price** (a second line — a new `cta_help_text`
field alongside `cta_label`/`cta_url` on `CourseAccessDecision`); and content unlocks with
`can_access_content=True` **without** a
`UserCourseRegistration` — the "access without enrolment" property the spec already calls
load-bearing (§4.4).

## 2. Buy a bundle (a group of courses)

*What it is:* one purchase unlocks a named set of courses.

**Student sees & does:** each course in the set shows something like
"Included in the Data Track — unlock 6 courses · $99" rather than its own price (or they reach a
bundle landing page). **One checkout unlocks every course in the set at once**; afterwards each
shows "Start"/"Continue". The decision shifts from "buy *this* course" to "buy *this track*" — a
learner may land on course A but pay for access to A–F.

**Educator:** defines which courses belong to a bundle and its price.

**Asks of the seam:** one decision affects **many** courses, so `get_access` reads ownership that
isn't stored on this course's own `access_config`; the CTA may point at a *bundle* page rather than
this course; `filter_visible()` and a "your tracks" dashboard panel surface what a purchase
unlocked.

## 3. Broad subscription

*What it is:* a recurring payment unlocks a tier of courses (some, or all) while it stays active.

**Student sees & does:** a non-subscriber sees "Subscribe to unlock" on every gated course.
Subscribing once (on a subscription page) **flips all included courses to "Start"** — from then on
they self-start anything in the tier exactly like a free course. If the subscription lapses, those
same courses revert to "Subscribe to unlock". The recurring decision is about the *subscription*,
made once, not per course. The dashboard carries a subscription-status / manage-plan panel.

**Educator:** defines the tiers and which courses each includes; billing is the backend's concern.

**Asks of the seam:** the same course flips between "Subscribe" and "Start" on **account state**
with no change to its `access_config` — the backend reads the *user's* subscription, not the
course. `filter_visible()` may hide or badge out-of-tier courses, and this is where a future
`has_feature()` (e.g. subscriber-only live chat) eventually hangs.

## 4. Prerequisites

*What it is:* a course stays locked until the learner has finished another.

**Student sees & does:** on the advanced course the CTA is **not actionable** — it reads
"Complete Foundations first" and links to the prerequisite course instead of starting anything. The
learner's decision is redirected: go finish the prerequisite. The moment the prerequisite is
complete, the CTA becomes "Start" on its own — no purchase, no application, no educator action,
just sequencing.

**Educator:** declares the prerequisite chain when authoring courses.

**Asks of the seam:** the CTA needs a genuine **disabled / informational** state whose label
explains *why* and whose `url` points at a *different course*; the decision is derived from
**progress** (`student_progress`), not from registration or `access_config`.

## 5. Profile gating

*What it is:* a learner can't enrol (anywhere, or in certain courses) until their account clears a
bar — verified email, completed profile, an uploaded ID / proof document.

**Student sees & does:** instead of "Start"/"Apply", the course shows
"Complete your profile to enrol", linking to a profile / verification page (fill required fields,
upload an ID). Once the profile passes the check, the original CTA ("Start" or "Apply") returns and
they proceed normally. The decision is account-level housekeeping, done **once**, that then unblocks
many courses. A "finish setting up your account" prompt could sit on the dashboard.

**Educator:** sets the required bar and reviews uploaded documents (detail out of scope here).

**Asks of the seam:** a gate that's about the **user**, not the course, and that often **layers in
front of another type** — a course can be both profile-gated *and* application-gated. So the seam
needs to express "this other gate must clear first" (gates that compose), plus a CTA that routes to
a profile surface.

## 6. Pre-assessments — a combination, not its own backend

A placement quiz / pre-assessment doesn't need its own access type. It's cleaner as either:

- **the application itself** — an application-gated course whose form is a scored quiz, auto-clearing
  when the score passes a bar (Coursera-style "performance-based admission"); or
- **a prerequisite** expressed as "score ≥ X on assessment Y" — same disabled-CTA UX as §4.

So its student UX is already covered by §4 / the application flow. Flagged here so the spec doesn't
invent a redundant fourth gate.

---

## What these ask of the access contract

Read together, the sketches stress the `CourseAccessDecision` contract (its flat `cta_label`/`cta_url`) in a few
specific ways. Most are already anticipated; one is genuinely new.

1. **Richer CTA** — a price or a short explanatory line (purchase, bundle, prerequisite, profile).
   Today the CTA is just `label` + `url`; the spec already says `help_text`/`variant`/`icon` get
   added "when a concrete backend needs them" — these are those backends.
2. **A non-actionable CTA state** — prerequisites and profile gating need a clearly *disabled* CTA
   that explains and links elsewhere. Confirm the existing `<c-button>` disabled path + a label that
   carries the reason covers it.
3. **Access without enrolment** — purchase and subscription grant `can_access_content` with **no**
   registration. Already called out as load-bearing (§4.4); these are *why* it matters.
4. **Decisions read account/user state, not just `access_config`** — subscription, prerequisites,
   and profile gating all derive the decision from things off the course. The seam already lets the
   backend look anywhere; just confirm nothing assumes `access_config` is the sole input.
5. **One decision, many courses** — bundles and subscriptions. `filter_visible()` and dashboard
   contributions carry this, not per-course CTAs alone.
6. **Gates that compose / stack** — profile-gate-*then*-apply, prerequisite-*then*-buy. This is the
   one genuinely new question: today one backend = one decision. Worth deciding in the spec whether
   a backend can chain gates, or whether composition is itself future work. *(Flag, don't solve.)*
7. **Every backend brings a dashboard panel** — owned courses, your tracks, subscription status,
   "finish your profile". `get_dashboard_contributions()` is the right seam; these confirm it earns
   its place.

**Bottom line:** every sketch stays "a new class + a settings change" and adds no new core surface —
which is the seam working as intended. The single thing to consciously decide in the spec is
**item 6 (composable gates)**; everything else is the contract flexing the way it was designed to.

---

## Architecture alternative considered: a registry of access-type handlers — rejected

A registry that maps each `access_type` to a self-contained handler was considered, on the theory
that future mechanisms would need to coexist and that subclassing would force a combinatorial tower
of classes. **This is wrong, and the registry is rejected as overcomplication.**

The model is one backend at a time, exactly like Django's `EMAIL_BACKEND` — you send mail through
one backend; there is no tower of email implementations depending on each other. Here, one
deployment runs one `COURSE_ACCESS_BACKEND`: an applications LMS runs the applications backend, a
subscriptions LMS runs the subscriptions backend. **They are never combined on one site**, so there
is no combination to enumerate and nothing for a registry to dispatch between.

What looks like "two types coexisting" is just the universal `free` baseline plus that backend's one
specialty. Every backend supports `free` (the default every existing course already has); the
applications backend adds `application_gated`, a subscriptions backend adds `subscription`. So
`ApplicationCourseAccessBackend` subclassing `DefaultCourseAccessBackend` (spec §5.5) is **depth 1,
not a chain** — inherit the free baseline, add one type. A subscriptions backend would subclass the
default the same way. They are siblings, each one class deep:

```
DefaultCourseAccessBackend              # free  (the baseline every backend inherits)
  ├─ ApplicationCourseAccessBackend     # free + application_gated     (applications LMS)
  └─ SubscriptionCourseAccessBackend    # free + subscription          (subscriptions LMS)
```

There is no `Subscription(Application(Default))` stack because no deployment wants both — so the 2ᴺ
problem the registry was meant to solve never arises. A registry would add a handler protocol, a
process-level dict, import-time registration side effects, and an `INSTALLED_APPS`-ordering concern,
all to dispatch a single backend between `free` and its one other type — which a trivial branch
already does. Keep subclassing `DefaultCourseAccessBackend`; it is the minimal, correct mechanism and
it matches the `EMAIL_BACKEND` precedent the spec is modelled on.

(Composition — item 6, profile-*then*-apply on a single course — remains the one genuinely open
question, and it is unaffected by this: it is a separate decision about stacking gates within one
backend, not about combining backends across a deployment.)
