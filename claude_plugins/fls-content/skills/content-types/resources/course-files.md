# COURSE, COURSE_PART, and COURSE_CATEGORIES Files

---

## COURSE (`course.md`)

One `course.md` file per course root directory. Its presence identifies the directory as a COURSE.

A course can contain COURSE_PARTs, but they are not required. Course parts are like sections or folders that group topics and forms. A course can also contain topics and forms directly, without any parts.

### Frontmatter fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `content_type` | `COURSE` | Yes | Must be exactly `COURSE` |
| `title` | `str` | Yes | Course display title |
| `subtitle` | `str` | No | Optional subtitle |
| `description` | `str` | No | Optional course description |
| `categories` | `list[str]` | No | Slugs of the categories (declared in `course_categories.yaml`) this course belongs to. Defaults to `[]`. See [Course categories](#course-categories) below. |
| `dashboard_category` | `str` | Conditional | The one category slug the learner dashboard files this course under. **Required when `categories` has two or more entries**, and must be one of them. With exactly one entry, that entry is used automatically. |
| `uuid` | `str` | No | Written by `content_save` — **omit on new files** |
| `icon` | `str` | No | Semantic icon name (e.g. `"notes"`) or literal glyph |
| `icon_fallback` | `str` | No | `"<iconset>:<glyph>"` (e.g. `"phosphor:drone"`); only valid when `icon` is also set |
| `learning_outcomes` | `list[str]` | No | "What you'll learn" bullet list |
| `difficulty` | `beginner`, `intermediate`, `advanced`, or `all_levels` | No | Difficulty level |
| `visibility` | `published`, `coming_soon`, or `hidden` | No | Course visibility lifecycle state. Defaults to `published` when omitted. |
| `table_of_contents_in_development` | `bool` | No | Hide the course's table-of-contents surfaces (Lessons stat card, the lesson-count line in "This course includes", and the "Course content" section) while the course is still being built. Defaults to `false`. Independent of `visibility`. See [Table of contents in development](#table-of-contents-in-development) below. |
| `estimated_duration` | `str` | No | Duration string e.g. `"1:30:00"` (HH:MM:SS) |
| `children` | `list` | No | Explicit ordered list of child paths; if omitted, auto-discovered alphabetically |
| `content` | `str` | No | Optional markdown intro body |
| `access_config` | `dict` | No | How learners get access to the course. See [Course access configuration](#course-access-configuration) below. Absent → `free`. |
| `price` | `dict` | No | What the course costs. Display only — no payment is processed. See [Course pricing](#course-pricing) below. Omit for no price. |
| `tags` | `list[str]` | No | Optional tag list |
| `meta` | `dict` | No | Arbitrary metadata |

### Minimal example (new course)

```yaml
---
content_type: COURSE
title: Introduction to Python
description: A beginner-friendly guide to Python programming.
---
```

### Full example

```yaml
---
content_type: COURSE
title: Standard Markdown - Demo
subtitle: A standard tour of the content system
description: This will show how all the Standard Markdown goodies show up.
difficulty: beginner
estimated_duration: "1:30:00"
icon: notes
learning_outcomes:
  - Understand how the markdown content system renders
  - Recognise every built-in content widget
  - Author a course with confidence
---

Your competitive advantage is your ability to learn.
```

### Children ordering

When `children:` is omitted, `content_save` auto-discovers children alphabetically from the directory. For custom ordering or to exclude specific files, use an explicit `children:` list:

```yaml
children:
  - path: 01. intro/content.md
  - path: 02. concepts/content.md
  - path: 03. quiz/form.md
```

### Course categories

`categories:` lists the slugs of the categories this course belongs to. Every slug must be
declared in the repo's single `course_categories.yaml` (see
[COURSE_CATEGORIES](#course_categories-course_categoriesyaml) below); an undeclared slug fails
validation:

```
Field: categories[0]
Problem: no category is declared with this slug in this content repo
Fix the slug, or add an entry declaring it in course_categories.yaml.
```

`dashboard_category` names the **one** category the learner dashboard files the course under:

- **One entry in `categories`** — `dashboard_category` is optional; that entry is used
  automatically when it is omitted.
- **Two or more entries** — `dashboard_category` is **required**, and must be one of the listed
  `categories`. Omitting it fails with *"this course belongs to two or more categories, so
  dashboard_category must name which one the dashboard uses"*; naming a slug outside
  `categories` fails with *"the dashboard category has to be one the course belongs to"*.
- **No entries** — the course belongs to no category, and the dashboard falls back to its
  built-in sections.

**A single category — no `dashboard_category` needed:**

```yaml
---
content_type: COURSE
title: Functionality Demo - show end with Quiz
categories:
  - assessment
---
```

**Two categories — `dashboard_category` picks one:**

```yaml
---
content_type: COURSE
title: Functionality Demo - show end with Topic
categories:
  - start-here
  - assessment
dashboard_category: start-here
---
```

### The retired `category` field

`category:` (singular) is **not** a course field. Writing it fails validation outright, even
when nothing else about the file is wrong:

```
'category' is no longer a course field. Use 'categories' (a list of category slugs), and
'dashboard_category' when there is more than one.
```

Rename it to `categories:` (a list), adding `dashboard_category:` if there is more than one
entry.

### Table of contents in development

`table_of_contents_in_development: true` hides three TOC surfaces on the course
detail page while the course is still being authored: the Lessons stat card,
the lesson-count line inside "This course includes", and the entire "Course
content" section. It has no effect on anything else — the course still renders
otherwise.

It is independent of `visibility` and composes with all three states. A
`published` course can carry it, which is what an application-gated course
needs: applications are open while the contents are still being written.

```yaml
---
content_type: COURSE
title: Being Built
table_of_contents_in_development: true
access_config:
  access_type: application_gated
---
```

Remove the flag (or set it back to `false`) once the contents are written.

### Course access configuration

`access_config` controls how a learner gains access to the course. It is an **opaque
configuration block** interpreted by the deployment's active course-access backend
(`COURSE_ACCESS_BACKEND`) — the content schema itself does not interpret its keys.

In practice you set a single `access_type`:

| `access_type` | Meaning |
|---|---|
| `free` | Open to everyone; learners self-enrol with one click. This is the **default** when `access_config` is absent. |
| `application_gated` | The learner must submit an application and be accepted before they can enrol. |

**A free course (the default) — just omit `access_config`:**

```yaml
---
content_type: COURSE
title: Introduction to Python
---
```

**Equivalently, free stated explicitly:**

```yaml
---
content_type: COURSE
title: Introduction to Python
access_config:
  access_type: free
---
```

**An application-gated course:**

```yaml
---
content_type: COURSE
title: Advanced Mentorship Programme
access_config:
  access_type: application_gated
---
```

**A gated course that asks applicants to fill in a form:**

```yaml
---
content_type: COURSE
title: Advanced Mentorship Programme
access_config:
  access_type: application_gated
  application_form: ../mentorship_application/form.md
---
```

`application_form` is the path to the FORM file an applicant fills in before their
application is reviewed, written **relative to this `course.md`**. It is optional: a gated
course without one just takes the application and shows the applicant a status page.

Two rules the host enforces at content-load:

- The path must resolve to a FORM that is loaded in the same run. Point it at a topic, or at
  a form outside the loaded content, and the load fails.
- `application_form` is only valid alongside `access_type: application_gated`. A free course
  naming a form is refused rather than quietly ignored.

The form is named here, **not** listed in the course's `children:`. An application form placed
in a course's content collection renders and behaves as a survey inside the course — which,
with `strategy: UNSCORED`, is exactly what it becomes. That is an authoring mistake the host
does not police.

**Which `access_type` values are valid is deployment-specific.** They come from the active
`COURSE_ACCESS_BACKEND` and are declared, per content repo, in `.fls-content.yaml` under
`access_types` (scaffolded by `/fls-content:init`). The FLS shipped default accepts `free`
and `application_gated`; a free-only deployment accepts only `free`; a custom backend may
define entirely different values.

**Invalid `access_config` is rejected — at both ends:**

- `/fls-content:validate-content` flags it offline against the repo's declared
  `access_types`. An unknown key (anything other than `access_type`) or an unrecognised
  `access_type` value fails validation, e.g.:

  ```yaml
  access_config:
    access_type: paid        # ✗ not a valid access type for this deployment
    price: 50                # ✗ unknown key — only `access_type` and
                             #   `application_form` are allowed
  ```

- The FLS host re-validates at content-load through the active backend, so bad config never
  reaches the database.

Set `access_config` deliberately — it is never inferred from course content. When editing an
existing course file, preserve any `access_config` exactly as written; do not invent, change,
or drop it.

### Course pricing

`price` declares what a course costs. It is **display only** — nothing here processes payment;
enrolment/access is controlled separately by `access_config` above. Omit `price` entirely for a
course with no price shown anywhere.

Every `price` has a `kind`, which selects one of four shapes. Each shape takes only its own
fields — writing a field another shape does not use fails validation with *"Not used by a
<kind> price."*, and omitting one it requires fails with *"Required for a <kind>
price."*

| `kind` | Required fields | Optional fields | Reads as |
|---|---|---|---|
| `fixed` | `amount` | `currency`, `tax_note` | One amount |
| `range` | `low_amount` | `high_amount`, `currency`, `tax_note` | A span; omit `high_amount` for an open-ended "From X" |
| `discounted` | `amount`, `sale_amount` | `sale_ends_on`, `currency`, `tax_note` | A struck-through original amount plus a sale amount, until an optional end date |
| `on_request` | — | — | No amount published; a visitor is told to ask |

#### Amount fields

`amount`, `sale_amount`, `low_amount` and `high_amount` are all the same kind of field:

- **Always write an amount as a quoted string**, e.g. `amount: "1499.00"`. An unquoted number
  (`amount: 1499.00`) is read through YAML's float parser before validation ever sees it and is
  refused outright: *"write amounts as quoted strings, e.g. \"1499.00\""*.
- Must be greater than zero, and finite.
- At most 3 decimal places, and below 1,000,000,000 — *"Can have at most 3 decimal places."* /
  *"Too large."*
- Cannot carry more decimal places than the resolved `currency` allows, e.g. `1500.50` in `JPY`
  fails with *"Has more decimal places than JPY allows."* (JPY has no minor units at all).
- On a `discounted` price, `sale_amount` must be less than `amount` — *"Must be less than the
  full amount."*
- On a `range` price with both ends set, `low_amount` must be less than `high_amount` —
  *"Must be greater than the low amount."* (reported against `high_amount`)

#### `currency`

An ISO 4217 code (e.g. `ZAR`, `USD`, `JPY`), validated against Babel's currency list — an
unrecognised code fails with *"'XXX' is not a recognised currency code."* `on_request` never
takes a `currency`.

If `currency` is omitted on a kind that needs one, the project's configured `DEFAULT_CURRENCY`
is used instead at save time. **The offline validator has no access to that setting**, so it
always skips the currency-precision check when `currency` is omitted from the file — even if
the project's `DEFAULT_CURRENCY` would have caught it. If the project has *no* `DEFAULT_CURRENCY`
either, saving the content fails at `content_save` time (not at validation time) with *"the
price has no currency and DEFAULT_CURRENCY is not set."* Write `currency` explicitly to avoid
depending on a setting the validator can't see.

#### `sale_ends_on`

An ISO date (`YYYY-MM-DD`), only valid on `discounted`. Once the date passes, the course shows
`amount` as a plain fixed price — the struck-through `sale_amount` disappears. Omit it for a
sale with no end date.

#### `tax_note`

A short free-text string (max 100 characters), e.g. `"incl. VAT"` or `"excl. tax"`. Shown on the
course page's sign-up panel only — never on cards or list rows.

#### Clearing a price

Omitting `price` entirely leaves whatever price is already stored on the course untouched —
same as `tags`. To remove a previously-set price, write `price: null` explicitly.

#### Examples

**A fixed price with a tax note:**

```yaml
---
content_type: COURSE
title: 'Functionality Demo - Price: fixed'
price:
  kind: fixed
  amount: "250.00"
  currency: USD
  tax_note: excl. tax
---
```

**An open-ended range ("From X"):**

```yaml
---
content_type: COURSE
title: 'Functionality Demo - Price: from'
price:
  kind: range
  low_amount: "500.00"
  currency: ZAR
---
```

**A low-high range:**

```yaml
---
content_type: COURSE
title: 'Functionality Demo - Price: range'
price:
  kind: range
  low_amount: "1200.00"
  high_amount: "3000.00"
  currency: ZAR
---
```

**A discounted price with a sale end date:**

```yaml
---
content_type: COURSE
title: 'Functionality Demo - Price: sale with an end date'
price:
  kind: discounted
  amount: "400.00"
  sale_amount: "300.00"
  sale_ends_on: 2099-12-31
  currency: EUR
  tax_note: incl. VAT
---
```

**No published amount:**

```yaml
---
content_type: COURSE
title: 'Functionality Demo - Price: on request'
price:
  kind: on_request
---
```

See `demo_content/functionality_demo_price_*/course.md` for the full set of worked examples,
including a currency with no minor units (`functionality_demo_price_zero_decimal`) and an
already-expired sale (`functionality_demo_price_sale_expired`).

---

## COURSE_PART (`part.yaml`)

One `part.yaml` file per course-part subdirectory. Its presence identifies the directory as a COURSE_PART. The directory must be numbered (e.g. `01. Getting Started/`).

**`part.yaml` has no closing `---`** — the file ends after the last key. This is valid single-document YAML.

### Frontmatter fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `content_type` | `COURSE_PART` | Yes | Must be exactly `COURSE_PART` |
| `title` | `str` | Yes | Part display title |
| `subtitle` | `str` | No | Optional subtitle |
| `description` | `str` | No | Optional description |
| `uuid` | `str` | No | Written by `content_save` — **omit on new files, and NEVER EDIT existing UUIDs** |
| `children` | `list` | No | Explicit ordered child list; if omitted, auto-discovered |
| `tags` | `list[str]` | No | Optional tag list |
| `meta` | `dict` | No | Arbitrary metadata |

Note: COURSE_PART has **no `content`** field — there is no markdown body on a part.

### Example (new part — no uuid)

```yaml
---
content_type: COURSE_PART
title: Getting Started
```

### Example (after content_save — uuid added)

```yaml
---
content_type: COURSE_PART
title: Getting Started
uuid: 66bb8510-ce90-426e-82fb-f02b7ca92fdc
```

Note the missing closing `---` — this is correct.

---

## COURSE_CATEGORIES (`course_categories.yaml`)

Declared **once per content repo**, in a file that lives outside every course directory —
normally the repo root, as a sibling of the course directories. It is identified by
`content_type: COURSE_CATEGORIES` rather than by filename, but name it `course_categories.yaml`
by convention. A second declaration anywhere in the repo, or one placed inside a course or
course-part directory, both fail validation:

- *"Multiple COURSE_CATEGORIES declarations found: [...]. A content repo may declare its
  categories only once."*
- *"COURSE_CATEGORIES declaration inside a course directory: [...]. Move it to the repo root."*

### Fields of each entry in `categories:`

| Field | Type | Required | Notes |
|---|---|---|---|
| `slug` | `str` | Yes | Stable identifier a course's `categories`/`dashboard_category` references. Letters, digits, hyphens, and underscores only. |
| `title` | `str` | Yes | Category display title |
| `description` | `str` | No | Optional description |
| `show_on_dashboard` | `bool` | No | Whether the dashboard gives this category its own section. Defaults to `true`. |
| `uuid` | `str` | No | Written by `content_save` — **omit on new entries, never hand-edit an existing one** |

An entry takes those five keys and nothing else — no per-entry `content_type`, `tags`, or
`meta`.

**Display order is the order of the entries in the list.** There is no `order:` field;
`content_save` assigns each category's order from its position.

### Rules

- Every `slug` in the file must be unique, and every `uuid` that is set must be unique.
  A copied entry that keeps its `uuid` loads as one row overwriting the other.
- A `slug` may only contain letters, digits, hyphens, and underscores.
- These slugs are reserved for the dashboard's built-in sections and may not be used:
  `in-progress`, `recommended`, `available`, `coming-soon`, `history`.
- **A category is identified by its `uuid`, not its slug.** To rename one, keep its `uuid` and
  change `slug`/`title` — then update every course that referenced the old slug. Dropping the
  `uuid` creates a second category instead of renaming the first.
- **A slug that collides with a category already in the database is only caught by
  `content_save`, not by `/fls-content:validate-content`** — the offline validator has no
  database to check against. `content_save` refuses the save, names the `uuid` that already
  owns the slug, and asks you to either adopt that category (copy its `uuid` into your entry)
  or choose a different slug.

### Example (new file — no uuids)

```yaml
---
content_type: COURSE_CATEGORIES
categories:
  - slug: start-here
    title: Start here
    description: New to the platform? Begin with these.
  - slug: assessment
    title: Assessment
    description: Courses that end in a graded quiz.
  - slug: reference
    title: Reference
    description: Reference material, listed in the catch-all rather than its own section.
    show_on_dashboard: false
---
```

After `content_save`, each entry gains a `uuid:` key — see `demo_content/course_categories.yaml`
for the saved form.

Directory layout reference: see [`file-layout.md`](file-layout.md).
UUID and numbering rules: see the `fls-content:conventions` skill.
