# Research: forms as their own app

## Executive summary

**Recommendation: no — do not extract forms into their own Django app.** Split
`content_engine/models.py` (and, opportunistically, `schema.py`/`admin.py`) into a
`models/` package with a `forms.py` module instead — same app label, same tables,
zero migration, most of the organisational benefit. The "forms feel complicated"
intuition is real but mis-locates the complexity: the hard parts (scoring,
attempts, resumability, quiz percentage, per-question answer state) already live
in `student_progress` (`FormProgress` is 407 of 571 model lines,
`student_progress/models.py:76-482`) and the player UI already lives in
`student_interface` (`view_form`/`form_fill_page` and neighbours,
`student_interface/views.py:828-1337`, with its own templates) — both already have
their own apps. What's left in `content_engine` is pure structural definition
(5 models, mostly title/order/FK fields), no more intrinsically complex than
`Course`/`CoursePart`'s own GFK-based `children()` tree, which nobody is proposing
to extract. Extraction is also expensive in a way that doesn't pay for itself
pre-deploy: the abstract-base coupling (`BaseContent`/`TitledContent`/
`MarkdownContent`, `content_engine/models.py:55-143`) has no good new home, the
single shared pydantic registry (`schema.py:70,335-336`) and single-pass importer
(`content_save.py:492-698`) would have to be forked or re-coupled, every model
table would be renamed for no functional gain (nothing sets `db_table`; app label
is `freedom_ls_content_engine`, `content_engine/apps.py:7`), and — the most
concrete finding — **six apps that already depend on `content_engine`
(`student_progress`, `student_interface`, `educator_interface`, `reports`,
`student_management`, `qa_helpers`, per `docs/app_structure.md:109-112,62-68,
83-88,103-108,74-82`) import `Form`/`FormPage`/`FormQuestion` directly and
interchangeably with `Topic`/`Course` in the same functions** (e.g.
`student_interface/views.py:421,423,712` branches `isinstance(current_item,
Form)` right next to `Topic` handling). Splitting forms out doesn't shrink
`content_engine`'s fan-in — it *doubles* it, giving every one of those six apps a
second edge to maintain instead of one. This would also actively complicate three
specs already queued against the current tree shape (`content_snapshots`,
`compliance-form-randomization`, `compliance-exam-remediation`) with no offsetting
benefit. Revisit only if a concrete reuse case for forms *outside* course content
ever appears — not to satisfy a feeling that a 605-line file is big.

## 1. The case for and against

**For, as stated in the idea:** forms are a genuinely deeper structure than the
rest of `content_engine`. `Form` → `FormPage` → (`FormContent` | `FormQuestion`) →
`QuestionOption` is a four-level tree (`content_engine/models.py:421-567`), versus
`Topic`/`Activity` which are flat leaves (`models.py:145-169`) and `Course`/
`CoursePart` which are one level of GFK-mediated children
(`models.py:232-237,353-358`). By line count, forms are 157 of 605 lines of
`models.py` (~26%), 130 of 336 of `schema.py` (~39%), 135 of 279 of `admin.py`
(~48%), 63 of 170 of `factories.py` (~37%), and 115 of 711 of `content_save.py`
(~16%) — a real, measurable share, and admin in particular is nearly half forms.
Forms also carry domain concepts nothing else in `content_engine` has: a scoring
`strategy` (`CATEGORY_VALUE_SUM`/`QUIZ`, `models.py:31-36`), quiz semantics
(`quiz_show_incorrect`, `quiz_pass_percentage`, `models.py:431-439`), and
attempt-lifecycle behaviour (`submit_on_exit`, `models.py:441-447`).

**Against:** almost none of that weight is *model* complexity — it's *file* share
driven by tree depth, not by any individual model being hard to reason about.
`FormPage` (`models.py:456-482`) has four real fields (`form`, `order`,
`category`, plus inherited title/slug); `FormQuestion` (`models.py:503-549`) has
six; `QuestionOption` (`models.py:552-567`) has four. None approaches `Course`
(`models.py:172-344`, 172 lines, `access_config`/icon validation/accent-slot
allocation/duration formatting) in per-model complexity, and nobody is proposing
to split `Course` out of `content_engine`. The genuinely hard behaviour that
*would* justify calling forms "complicated" — incomplete-attempt tracking,
stale-attempt finalisation, per-question answer persistence, quiz percentage and
pass/fail, resumability — is **already** factored into `student_progress`
(`FormProgress`, `student_progress/models.py:76-482`, plus
`student_progress/scoring.py`, `submissions.py`, `queries.py`) and
**already** has its own player views and templates in `student_interface`
(`student_interface/views.py:828-1337`; "No form templates live in content_engine
at all" per the task's verified facts). That is: the definition/attempt split the
idea seems to be reaching for **already exists**, one layer up, as separate apps.
What remains inside `content_engine` is the authoring-time shape only, and it is
not disproportionately hard to that layer's existing job.

**Verdict:** the "it feels complicated" signal is correctly diagnosing that forms
carry more *structure* than other content types, but incorrectly locates the fix
as an app boundary. The fixed constraint — "not looking for scope creep and fancy
features... we are just aiming to clean up the database structure" — argues for
the cheapest change that relieves the actual pain (file navigability), not the
most structurally disruptive one.

## 2. The concrete cost of extraction

**Abstract-base coupling.** `Form` is `TitledContent, MarkdownContent`; `FormPage`
is `TitledContent`; `FormContent` is `MarkdownContent`; `FormQuestion` is the bare
`BaseContent` (`models.py:421,456,485,503`). Only `QuestionOption` is a plain
`SiteAwareModel` (`models.py:552`). Three options, none good:
1. **Move `BaseContent`/`TitledContent`/`MarkdownContent` down to
   `site_aware_models`.** These are content-authoring concepts — `file_path`,
   `meta`, `tags` (`models.py:60-67`), `slug` (`models.py:112-115`), markdown
   `content` + `rendered_content()` (`models.py:127-139`) — not generic
   site-scoping concepts. `site_aware_models` today is deliberately generic (one
   `site` FK, one UUID PK, `models.py` in that app is 84 lines with zero
   authoring vocabulary). Moving them down pollutes a foundational, currently
   clean layer with course-content-specific fields for the sole benefit of one
   app split, and `Topic`/`Activity`/`Course`/`CoursePart` would still import
   from that lower layer too — so this doesn't even localise the change to forms.
2. **Keep the bases in `content_engine`, import them from a new `forms` app.**
   This adds a `forms --> content_engine` edge for the bases alone, while
   `content_engine` keeps needing to know about forms anyway (see the fan-in
   point below) — a net *increase* in edges, not a reduction.
3. **Duplicate the three abstract bases in the new app.** Directly contradicts
   the project convention "avoid repeating code... favor extracting it into a new
   function/class" (`CLAUDE.md`).

**Shared pydantic registry.** `schema.py`'s `SCHEMAS = BaseContentModel._registry`
(`schema.py:70,335-336`) is populated by every content type's
`__init_subclass__`, forms included (`schema.py:223-329`). There is one registry,
consulted by `validate.py`'s single content-tree walk. Splitting `Form`/
`FormPage`/`FormContent`/`FormQuestion` schema classes into a separate module
either keeps registering into `content_engine`'s shared `_registry` (an
import-time coupling back into `content_engine`, regardless of which app the
class textually lives in) or forks the registry, which then has to be walked
twice and reconciled — real new coupling either way, not a clean cut.

**Single-pass importer.** `content_save.py`'s `save_content_to_db`
(`content_save.py:492-698`) builds one `content_by_path` dict spanning topics,
activities, courses, course parts, *and* forms/pages/questions/content in a
single function (`content_save.py:517-604`), then resolves `Course`/`CoursePart`
children generically against that combined map (`content_save.py:605-696`) —
a `Form` is just another entry a `Course` might point at. Splitting forms out
means either forking this into two coordinating importers that share the path
map across an app boundary (real coupling, not a reduction) or leaving
`content_save.py` in `content_engine` and having it reach into the new `forms`
app for five of its nine save functions (`save_form`, `save_form_page`,
`save_form_content`, `save_form_question`, `content_save.py:355-417`) — again a
`content_engine --> forms` edge that has to exist for the walk to work at all.

**The GFK child relationship is a non-issue, not a blocker or a benefit.**
`ContentCollectionItem`'s `child` `GenericForeignKey` (`models.py:400-404`)
resolves via Django's `ContentType`, which is keyed by `app_label` + model name —
it does not care which app a child model lives in. So the GFK mechanism itself
would keep working unchanged if `Form` moved apps. But this cuts both ways: it
means the GFK was never an obstacle to begin with, so "the GFK makes forms
special" is not a reason to extract them either — `Topic`/`Activity` already
prove arbitrary content types can be GFK children without needing their own app.

**Table renames.** No model in `content_engine` sets `db_table`; table names
derive from `label = "freedom_ls_content_engine"` (`content_engine/apps.py:7`),
confirmed by grepping the migrations directory for `db_table` (no matches). Every
form-related table (`freedom_ls_content_engine_form`,
`..._formpage`, `..._formcontent`, `..._formquestion`, `..._questionoption`)
would be renamed under a new app label. Per the fixed constraint, this repo has a
sibling spec covering squash-vs-rewrite migration mechanics — this research only
flags that an extraction **is** a table-rename event; sequencing it is out of
scope here.

**New/changed edges in `docs/app_structure.md`.** This is the most concrete
finding. Grepping the whole tree for `Form`/`FormPage`/`FormQuestion`/
`FormContent` imports shows they are used directly, not just via
`content_engine`, in: `student_progress` (`submissions.py`, `queries.py`,
`models.py`), `student_interface` (`views.py`, `utils.py`, `apis.py`),
`educator_interface` (`views.py`), `reports` (`gather.py`, `indexes.py`),
`student_management` (`deadline_utils.py`), and `qa_helpers` (multiple
management commands). Every one of these six apps **already** has a `--> content_engine`
edge in `docs/app_structure.md` (`student_progress --> content_engine`
line 110; `student_interface --> content_engine` line 94; `educator_interface -->
content_engine` line 62; `reports --> content_engine` line 85; `student_management
--> content_engine` line 105; `qa_helpers --> content_engine` line 75). If `Form`
et al. moved to a new `forms` app, **all six would need a second edge added**
(`--> forms`), because each of them uses `Form` interchangeably with `Topic`/
`Course` in the same code paths (e.g. `student_interface/views.py:421,423,712`
does `isinstance(current_item, Form)` right beside the `Topic` branch that stays
in `content_engine`). `content_engine` itself would also gain a `--> forms` edge
back (for `content_save.py`'s importer and `content_tags.py`, which references
form content types per the earlier grep). Net effect: **content_engine's fan-in
does not shrink — the graph gains at least seven new edges** (six consumer apps +
`content_engine` itself) for the same total amount of coupling, just spread
thinner. That is a strictly worse position for `docs/app_structure.md` legibility,
which is the exact thing this cleanup is supposed to improve.

## 3. Alternatives short of a new app

**Split `content_engine/models.py` into a `models/` package** — e.g.
`models/base.py` (`BaseContent`/`TitledContent`/`MarkdownContent`/enums),
`models/content.py` (`Topic`/`Activity`), `models/course.py` (`Course`/
`CoursePart`/`ContentCollectionItem`), `models/forms.py` (`Form`/`FormPage`/
`FormContent`/`FormQuestion`/`QuestionOption`), `models/files.py` (`File`), all
re-exported from `models/__init__.py` so every existing `from
freedom_ls.content_engine.models import Form` import keeps working unchanged.
Same app label, same `db_table` derivation (Django does not care whether a model
class is defined in `models.py` or `models/forms.py`, only which app config owns
it), **zero migrations**, zero new cross-app edges. `schema.py` and `admin.py`
could get the same treatment (a `schema/forms.py`, `admin/forms.py`) if the
198-line admin.py forms share is the actual pain point. This gets essentially all
of the stated benefit — "forms are complicated enough that they deserve their own
file(s)" — for none of the migration/graph cost above. **This is the recommended
do-now action**, and it is safe precisely because it changes nothing at the
database or import-graph level, only file layout.

**Say plainly:** yes, this gets most of the benefit for none of the migration
cost. The only thing a `models/` package split does *not* buy that a real app
split would is an independent test suite / independent `INSTALLED_APPS` toggle
for forms — and nothing in the idea, or in FLS's downstream-submodule usage model
per `docs/product/deployment.md`, suggests any concrete need for that today.

## 4. Interaction with queued work

- **`content_snapshots`** (`spec_dd/2. in progress/content_snapshots/0. idea.md`):
  explicitly scopes itself to depend on "no other freedom_ls app beyond
  `content_engine` (and `accounts`/`site_aware_models` where the base classes
  require it)" (idea.md line 23), and its own text calls the `Form` →
  `FormPage` → `FormContent`/`FormQuestion` tree its hardest snapshot target
  (idea.md lines 6-7, 33). If forms moved to a separate app, that spec's stated
  dependency contract would immediately need widening to `content_engine +
  forms`, on the same day the extraction lands, for no benefit to the snapshot
  work itself (a snapshot walk over the tree doesn't care which app the
  models live in). **Extraction makes this spec strictly worse to implement**,
  since it would need to walk two apps' models instead of one to build a single
  snapshot of a `Form`.
- **`compliance-form-randomization`** (`spec_dd/2. in progress/
  compliance-form-randomization/idea.md`): adds a new `FormGroup`-shaped
  sub-page primitive sitting between `FormPage` and its items (idea.md lines
  37-45, 87-90), plus a per-attempt realized-order record. The new group model
  naturally lives wherever `FormPage` lives today — a `models/forms.py` module
  handles this cleanly with zero friction; a separate app handles it exactly
  the same, so this spec is **neutral** on the app-boundary question. It is,
  however, evidence that the form model surface is actively growing right now —
  which is itself an argument for **not** compounding an active growth spurt
  with an app-boundary rewrite, not an argument for doing the extraction first.
- **`compliance-exam-remediation`** (`spec_dd/1. next/
  compliance-exam-remediation/idea.md`): "reference relevant content" for
  per-answer explanations (idea.md line 8) most naturally means a `FormQuestion`
  or per-option field referencing a `Topic`/`Activity` (or a `File`) elsewhere in
  `content_engine`. That is a **new pointer from forms into the rest of
  content_engine's non-form models** — exactly the kind of intra-`content_engine`
  reference that an app split would turn into a cross-app edge
  (`forms --> content_engine`) where today it would just be an ordinary FK.
  **This spec argues against separation**, not for it.
- **`better_course_progress_tracking`** (`spec_dd/2. in progress/
  better_course_progress_tracking/idea.md`): re-keys `FormProgress` to the
  `ContentCollectionItem` placement rather than the bare `Form`
  (idea.md lines 74-90). This lives entirely in `student_progress` and treats
  `Form` exactly the way it already treats `Topic` — "just another content type
  behind a placement." It neither needs nor benefits from forms having their own
  app; if anything it reinforces that `student_progress` is already the correct
  home for form-specific *complexity*, while `content_engine` only needs to keep
  being a source of content-type definitions.

**Net across all four:** none of the queued work needs a forms app to land
cleanly, and two of the four (`content_snapshots`, `compliance-exam-remediation`)
would be made measurably harder by one.

## 5. Prior art

**`extract-icons-app`** (`spec_dd/1. next/extract-icons-app/idea.md`) is the
in-repo precedent for *doing* an app extraction, and it is instructive by
contrast rather than by parallel. That extraction is justified by genuine
external reuse value ("Pull `freedom_ls/icons/` out... so it can be reused in
other Django projects," idea.md line 5) and the icons app has **no model
coupling into the rest of FLS at all** — it is a rendering/config layer with its
own Cotton component, no FKs to or from any domain model. The spec's own scope
section is dominated by closing genuine package-boundary gaps (hardcoded
`node_modules` assumption, template-namespace collision, SVG sanitisation) that
only matter because the target is a *standalone, installable* package consumed
by projects that are not FLS. Forms have neither property: there is no stated
reuse case outside FLS's own course-content tree, and — per §2 — forms are
tightly coupled via shared abstract bases, a shared pydantic registry, a shared
importer, and (per §2's fan-in analysis) six existing consumer apps that use
`Form` interchangeably with other `content_engine` types. The icons precedent
argues **for** extraction when the target is genuinely decoupled and has
external reuse value; it argues **against** extraction here, where neither
condition holds.

**`debt_markdown_rendering_package_isolation`** (`spec_dd/1. next/
debt_markdown_rendering_package_isolation/idea.md`) states the project's
boundary philosophy directly: "Don't invent throwaway models or undertake large
refactors just to purify the graph... 'inherent' is a legitimate verdict" (idea.md
lines 20-22). That spec is about removing *incidental* test-only edges, not about
model placement, but the governing principle transfers directly: a large,
migration-bearing refactor undertaken purely because a file looks big, when the
underlying coupling is inherent (shared bases, shared registry, shared importer,
six-app fan-in), is exactly the kind of refactor that guidance counsels against.

## 6. Brief external check

Comparable systems separate *authored content* from *assessment definitions* only
when there is a genuine reuse driver, and the shape of the separation is usually
narrower than "put the whole quiz model in its own module/app":

- **Moodle** originally kept quiz questions inside quiz-specific tables, then in
  Moodle 1.6 moved question code into a top-level, quiz-independent `question`
  bank so that other activity types (not just quizzes) could reuse questions from
  a shared category hierarchy tied to course/context — the driver was **cross-activity
  reuse of individual questions**, not "the quiz module felt too big" ([Quiz
  database structure — MoodleDocs](https://docs.moodle.org/dev/Quiz_database_structure);
  [Question database structure — MoodleDocs](https://docs.moodle.org/dev/Question_database_structure)).
  FLS has no analogous reuse driver today — `compliance-form-randomization`'s
  pools are explicitly scoped to a single form for V1 ("V1 pools belong to a
  single form," `compliance-form-randomization/idea.md` line 80) — so the Moodle
  precedent, if it applies at all, argues for a future *question-bank* concept
  scoped *within* forms, not for hoisting `Form` itself out of `content_engine`.
- **Open edX** does draw its content/assessment line differently — every unit of
  course content, quiz or otherwise, is a self-contained "XBlock" component with
  its own model, view, and handler, runnable and reusable independently of any
  specific course ([Introduction to XBlocks — XBlock API Guide](https://docs.openedx.org/projects/xblock/en/latest/xblock-tutorial/overview/introduction.html);
  [Open edX Platform Architecture](https://docs.openedx.org/en/latest/developers/references/developer_guide/architecture.html)).
  That is a wholesale plugin architecture, not an incremental app split, and
  adopting it would be the definition of the scope creep the idea explicitly
  rules out ("we are not looking for scope creep and fancy features at this
  point," idea.md line 12).

Neither precedent supports "give the LMS's existing form/quiz models their own
Django app" as an isolated, low-risk move; the one system that did separate
questions did so for a specific reuse capability FLS has explicitly deferred.

## Risks and gotchas

1. **Extraction would widen, not narrow, the app graph.** Per §2, six existing
   `content_engine` consumers (`student_progress`, `student_interface`,
   `educator_interface`, `reports`, `student_management`, `qa_helpers`) import
   `Form`/`FormPage`/`FormQuestion` directly, alongside `Topic`/`Course` from the
   same call sites. A forms app adds a second edge to each of them plus a
   `content_engine --> forms` reverse edge for the importer/registry — the
   opposite of the stated cleanup goal.
2. **The abstract-base question has no good answer.** All three options in §2
   (move bases down, import back up, duplicate) either pollute a clean
   foundational layer, add the very edge the split was meant to avoid, or violate
   the project's no-repeated-code convention. Any plan that proposes forms
   extraction must resolve this explicitly, not gloss over it.
3. **Table renames are a real migration event with no functional payoff.**
   Confirmed no `db_table` overrides exist anywhere in `content_engine`
   (`content_engine/apps.py:7`, migrations grep). This spec does not decide
   squash-vs-rewrite mechanics (a sibling spec's job), but any future forms-app
   proposal must be costed as "N table renames" up front.
4. **Two in-flight specs would be made harder, not easier.** `content_snapshots`
   would need to widen its own declared app-dependency contract
   (`content_snapshots/0. idea.md` line 23) the day extraction lands, for a
   spec whose hardest target is precisely the tree that would move.
   `compliance-exam-remediation`'s "reference relevant content" requirement
   points a form field at the rest of `content_engine` — a new cross-app pointer
   that doesn't exist today. Neither of these is fatal, but both are net costs
   with no offsetting gain, at exactly the pre-deploy moment this cleanup is
   trying to reduce risk, not add it.
5. **The `models/` package alternative (§3) is not risk-free either, just far
   cheaper.** Splitting one 605-line `models.py` into a package still needs
   care around import order (`FormPage` imports `Form`, etc.) and around
   re-exporting every name through `models/__init__.py` so the ~35+ files that
   do `from freedom_ls.content_engine.models import Form` keep working
   unchanged — but this is a mechanical, single-PR, zero-migration change, not a
   multi-spec coordination problem.
6. **Do not let "forms feel complicated" become a proxy for "the attempt/scoring
   layer feels complicated."** `student_progress`'s `FormProgress` genuinely is
   the most complex model in the codebase by line count (407 of 571 model lines,
   `student_progress/models.py:76-482`) — but it already has its own app. If
   there is real appetite for reducing perceived forms complexity, the highest-leverage
   move is auditing `student_progress`'s internal organisation (it already has
   `scoring.py`, `submissions.py`, `queries.py` alongside `models.py`), not moving
   `content_engine`'s comparatively simple definition models anywhere.

status: ok
