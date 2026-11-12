# FreedomLS voice

How FreedomLS sounds, in UI text, error messages, docs, README and marketing.

## Personality

- More **technical** than friendly: developer-to-developer, and open to newcomers.
- More **confident** than humble: clear convictions about learner-first design.
- More **opinionated** than neutral: strong views on pedagogy and portability, flexible on implementation.
- Balanced between **serious** and **playful**: professional with dry wit.
- Slightly more **raw** than polished: substance over style, and still careful.

## Voice principles

1. **Show, don't tell**: back every claim with a specific (a technology, a code example, a number). Rather than calling FreedomLS "extensible", show the snippet that extends it.
2. **Direct over diplomatic**: "FreedomLS stores content as Markdown files", not "FreedomLS leverages an innovative content paradigm."
3. **Teach while you talk**: even marketing copy leaves the reader knowing something new.
4. **Respect the reader's time**: front-load the important information, and prefer a code example to a long explanation.

SaaS phrasing marks copy that has drifted off-voice: "unlock potential", "empower learners", "drive engagement", "cutting-edge", "robust", "scale your learning". Replace each with the specific thing it gestured at.

## Tone by context

| Context             | Tone |
|---------------------|------|
| GitHub README       | Confident, concise, technical. Lead with what it does, then how. |
| Marketing site      | Slightly warmer, benefit-led, still grounded in specifics. Screenshots are of the real app. |
| Error messages      | Human, brief, helpful. Name the problem, suggest the fix, leave blame out. |
| Docs / tutorials    | Patient, thorough. Assume competence, not familiarity. Include the "why". Contributor docs are written for someone new to Django. |
| Community (Discord) | Casual, collegial, encouraging. Credit contributors by name and welcome first-timers warmly. |
| Conference talks    | Energetic but grounded. Open with a real problem, show real solutions. |

In every context, FreedomLS is a community open-source project: acknowledge its limitations honestly.

## Terminology

The words FreedomLS uses about itself in UI copy, docs and marketing. For the names of models, fields and other code concepts, `Skill(fls-dev:domain-glossary)` is canonical.

| Use this        | Instead of                | Why |
|-----------------|---------------------------|-----|
| extend          | customise                 | A foundation you build on, not a product you tweak |
| content         | curriculum                | Broader, less institutional, no rigid pedagogical assumption |
| learners        | students                  | Works across corporate, self-paced, and academic contexts |
| builders        | administrators            | People who deploy FreedomLS are building, not managing |
| learning system | LMS (where possible)      | Deliberately drops "Management": the system is for learning |
| fork it         | get started               | Culturally resonant, implies ownership from day one |
| foundation      | platform / solution       | Something you build on, not SaaS-speak |
| plain Markdown  | CMS / content management  | Explicit about the format |

## Dates and times

One format everywhere a person reads a date: `3 Nov 2026` for a date and `3 Nov 2026, 07:37` for a date-time, in the viewer's time zone, 24-hour clock, no ordinal and no "a.m.". Render a date with `<c-date>` and a date-time with `<c-datetime>`, and a deadline the learner reads in their own zone with `{% local_time %}`; the components hold the format, so a template never writes one. Never leave a date to the locale default (`Nov. 3, 2026, 7:37 a.m.`).

## Error messages

Name the specific problem, suggest a specific fix, in plain language. Explain any code you show. Routine actions end on a full stop.

```
✅ "Could not find the course file. Expected a course.md in /courses/my-course/"
❌ "Error: Invalid course configuration detected."

✅ "This email is already registered. Try signing in, or use a different email."
❌ "Error 409: Duplicate entry."

✅ "Progress saved. You're 60% through this module."
❌ "Success! Your learning journey progress has been updated."
```

## Dialogs and list pages

- A list page opens with its heading and its toolbar, so the list starts at the top. Help for the
  page lives in a dialog the page opens, or in the docs.
- A confirm dialog states what is true now and what the action changes. The person confirming
  reads the before and the after. A role confirm states the role's description and scope and
  nothing else: no paragraph of help.
- Every sentence in a confirm is true after the action. A sentence that describes the result
  matches what the action does, and no sentence promises something the change takes away.
- A confirm addresses the person as "you" when they act on themselves: "Deactivate your
  Organisation admin role?", "You lose…", "You keep…".
- A button in the middle of a multi-step dialog says "Next". The final button of a confirm step
  says "Confirm", or names the change when the noun is always true. A button names what the
  person does, never the system's step ("Look up"), and never a noun that may be untrue for this
  person ("Add staff member" for someone already on the staff).
- A disabled action shows its reason beside the control, and the control names it with
  `aria-describedby`.
- Two buttons in one row never share a bare verb. Each names its noun.
- One word for a relation everywhere it appears: a list and a quick view both say "via".
- Adding a record by hand is a form for one record, with "Add" and "Add and add another". A
  textarea that asks for one record per line is an import wearing a form's clothes.

This is how it sounds in FLS.

```
✅ "Current cohort: Cohort A. Sam Dlamini will be removed from Cohort A and added to the cohort you choose."
❌ "Are you sure you want to move this learner?"

✅ Generate a new report, disabled, with "Cohort A has 7 learners, over the report's learner limit of 5." beside it
❌ Generate a new report, enabled, then a red "Try again"

✅ A Staff page that opens with its heading, search and filters
❌ A Staff page that opens with a paragraph explaining what staff are

✅ Removing your own Organisation admin: "You lose Organisation admin… Someone who can give this role can give it back to you."
❌ Removing your own Organisation admin: "They lose Organisation admin… You can give the role again later."

✅ "Deactivate role" beside its role, and "Deactivate staff member" in the row's last column
❌ "Deactivate role" and "Deactivate" in the same row

✅ An email field with "Next", then a role step, then a confirm with "Confirm"
❌ An email field with "Look up", then a confirm with "Add staff member" for someone already on the staff

✅ "Course Pub" over "via Cohort A", with "40%" at the end, in the quick view and the Registrations list alike
❌ "Course Pub — through Cohort A — 40%"

✅ An "Add learner" form with Email, First name, Last name, Cohort and the buttons "Add" and "Add and add another"
❌ A textarea with "One per line: email, first name, last name"
```

The glossary's "staff member" is the noun on every button and dialog about an `StaffMember`:
"Deactivate staff member", "Reactivate staff member", and "Add staff member" on the button that
opens the add dialog.

## Naming

- **Features and apps**: plain, descriptive Django app names like `learner_progress` or `content_engine`. The "freedom" metaphor stays with the product name; features get ordinary names.
- **Releases**: semantic versioning (`v1.2.0`). Optionally, a major release takes a short code name from a place known for learning or free expression ("Alexandria", "Timbuktu"). Keep it subtle.

## Co-branding

- **Powered-by badge**: organisations using FreedomLS may show "Powered by FreedomLS" in a footer or about page, with the logo mark in Ocean or Midnight, at least 120px wide.
- **White-label**: learner-facing UI carries the deploying organisation's brand. FreedomLS attribution belongs in the footer, admin, or about page only.
- **Forks**: use their own branding and show lineage with "built on FreedomLS". A fork's name leaves out "Freedom".

## Sample copy

**Homepage hero:**
> Teach the way your learners need.
>
> Most learning platforms are digital textbooks: linear, rigid, and full of opinions about how learning should work. FreedomLS is an open-source learning system built with Django that lets you shape the platform around your learners, not the other way around.

**GitHub description (one line):**
> An open-source learning system built with Django. Learner-first, Markdown-native, Git-friendly, and endlessly extensible. Not another digital textbook.

**Error page (404):**
> This page doesn't exist — but that's fine, you can build whatever you need. Head back to [your dashboard] or [browse courses].

**Empty state (no courses):**
> No courses yet. Drop some Markdown files into your content directory and add a course.md to get started. [See the docs →]

## Visual checklist

- A confirm dialog says "you" when the person acts on themselves, and every sentence in it holds
  after the action: nothing it describes differs from the result, nothing it promises is lost by it.
