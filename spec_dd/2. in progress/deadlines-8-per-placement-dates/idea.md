# Per-placement due dates for shared content

Spec 8 of 8 in the Deadlines effort. Read the "Deadlines" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

A course author can give a topic, form or whole part a due date that applies only where it is
placed. Today a due date is written in the child's own file, so a topic placed in two courses
carries the same date in both, and a part placed in two courses carries its items' dates in both.
After this spec, a `children:` entry in `course.md` or `part.yaml` can carry a due date for that
one placement, which beats the child file's own value there and nowhere else. A part shared by two
courses can then have deadlines in one course and none in the other, and a staff override on top
still wins.

## Why

Spec 1's Decision 2 put content defaults on the child's own file, not on the `children:` list,
because every demo course auto-discovers its children and has no `children:` entry at all. That
holds for a course that owns its content. It fails as soon as a part is reused: the product owner
wants the same part placed in a short course with tight dates and in a long course with none, and
today the only remedy is a staff override per cohort registration or per learner, repeated for
each item of the part and each cohort that runs it.

## What is settled

- **The placement carries the override.** A `children:` entry can hold the same three fields the
  child file can, `due_date`, `due_time` and `due_days_after_registration`, with the same
  validation (`DueDateFields`). The entry's value beats the child file's for that collection
  item only. The `Child` schema already takes an object with `path` and an unused `overrides`
  dict; the due fields become first-class keys on the entry, not keys inside `overrides`.
- **A part placement can set dates for the part's items.** A `course.md` entry whose child is a
  part names the part's items by their path relative to the part and gives each a value. The
  part's own item rows are shared by every course that places the part, so a per-course value
  cannot live on those rows; it belongs to the course→part placement and the resolver reads it
  as the content layer for that course. Staff overrides sit above it as they do today.
- **Content loading writes it.** A load resolves each named path to the item it places and
  stores the value where the resolver reads it, every sync, so removing a key removes the value
  (spec 1's rule for the item columns and for `time_limit_days`). A path that names nothing in
  the part fails the load, as an unknown child does today.
- **The admin shows which value applies.** The override inlines' "Content default" column shows
  the placement's value when one is set, and the "Default has changed" comparison uses it, so a
  moved placement value is reported like a moved file value.
- **Decision 2 of spec 1 is revised, not reversed.** The child file is still where a date lives
  when the content is placed once. The `children:` entry is the place for a date that depends on
  where the content sits.
- **Auto-discovered courses are untouched.** A course with no `children:` list behaves exactly as
  after spec 1.

## Open until the spec

- **Where a part placement's per-item values are stored**: a column or JSON on the course→part
  `ContentCollectionItem`, or a row per (course, item). The resolver's query count must stay
  independent of the number of items, as spec 1 requires.
- **Whether `ContentCollectionItem.overrides` is repurposed or retired.** It is written on every
  load and read by nothing but the admin; the spec decides whether the due fields replace it.
- **Whether a part placement may also carry one value for every item of the part**, as a
  shorthand, or only named items.
- **The author plugin's wording.** `course-files.md`, `topic-files.md` and `form-files.md` in
  `claude_plugins/fls-content` say today to write due dates in the child file and not in
  `children:`. The spec rewrites them and the validator schema the plugin keeps.

## Out of scope

- Dates on an `ACTIVITY` or `ARTICLE` placement; a time limit on a part.
- Any change to the staff override layers, the policy or extensions (specs 1 to 3).
- Pruning stale placements on re-import.

## Resources

- `spec_dd/2. in progress/deadlines-1-dates-and-overdue/1. spec.md`: Decision 2, the content
  default columns and the resolver's layer order.
- `freedom_ls/content_engine/schema.py`: `Child`, `Course.children`, `CoursePart.children`;
  `freedom_ls/content_base/schema.py`: `DueDateFields`.
- `freedom_ls/content_engine/management/commands/content_save.py`: the collection item sync
  and `due_date_columns`.
- `freedom_ls/deadlines/resolver.py`: `_defaults_by_course`, where a shared part's rows are
  credited to every course that places it.
- Skills: `domain-glossary`, `fls-dev:markdown-content`, `fls-dev:admin-interface`,
  `fls-dev:testing`.
