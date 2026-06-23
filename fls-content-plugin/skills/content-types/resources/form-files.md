# FORM, FORM_PAGE, FORM_QUESTION, and FORM_CONTENT Files

A form lives in a **numbered subdirectory** (e.g. `03. quiz/`) containing:
- Exactly one `form.md` — the FORM
- One or more numbered `.yaml` files — each contains FORM_PAGE + questions/content

---

## FORM (`form.md`)

### Frontmatter fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `content_type` | `FORM` | Yes | Must be exactly `FORM` |
| `title` | `str` | Yes | Display title |
| `strategy` | `QUIZ` or `CATEGORY_VALUE_SUM` | Yes | Form scoring strategy |
| `quiz_show_incorrect` | `bool` | Conditional | Required when `strategy: QUIZ`; **must be absent** for `CATEGORY_VALUE_SUM` |
| `quiz_pass_percentage` | `int` (0–100) | Conditional | Required when `strategy: QUIZ`; **must be absent** for `CATEGORY_VALUE_SUM` |
| `submit_on_exit` | `bool` | No (default `false`) | If `true`, partial attempt is finalised on navigation away |
| `subtitle` | `str` | No | Optional subtitle |
| `description` | `str` | No | Optional description |
| `uuid` | `str` | No | Written by `content_save` — **omit on new files** |

### QUIZ example

```yaml
---
content_type: FORM
strategy: QUIZ
title: Module Knowledge Check
quiz_show_incorrect: true
quiz_pass_percentage: 80
---
```

### Survey (CATEGORY_VALUE_SUM) example

```yaml
---
content_type: FORM
strategy: CATEGORY_VALUE_SUM
title: Course Feedback Survey
---
```

---

## FORM_PAGE (first section of a page YAML file)

Page YAML files are named with a numeric prefix: `1. page.yaml`, `2. results.yaml`.

The **first** `---`-delimited YAML section is the FORM_PAGE.

### Frontmatter fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `content_type` | `FORM_PAGE` | Yes | Must be exactly `FORM_PAGE` |
| `title` | `str` | Yes | Page heading |
| `subtitle` | `str` | No | Optional subtitle |
| `description` | `str` | No | Optional instruction text |
| `uuid` | `str` | No | Written by `content_save` — **omit on new files** |

### Example FORM_PAGE section

```yaml
---
content_type: FORM_PAGE
title: Feedback
description: Tell us what you thought of this course.
```

Note: there is no closing `---` at the end of this first section when followed by question sections — the next `---` opens the next section.

---

## FORM_QUESTION (subsequent sections with a `question` key)

**FORM_QUESTION and FORM_CONTENT inherit a smaller base model** — they have **no** `title`, `subtitle`, `description`, `category` (as a display field), or `image` fields.

The parser selects `FORM_QUESTION` when a subsequent section contains a `question` key.

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `question` | `str` | Yes | The question text |
| `type` | `multiple_choice`, `checkboxes`, `short_text`, or `long_text` | Yes | Question type |
| `required` | `bool` | No (default `true`) | Whether the question must be answered |
| `category` | `str` | No | Used by `CATEGORY_VALUE_SUM` scoring strategy |
| `options` | `list` | Conditional | Required for `multiple_choice` and `checkboxes` |
| `uuid` | `str` | No | Written by `content_save` — **omit on new files** |
| `meta` | `dict` | No | Optional metadata |
| `tags` | `list[str]` | No | Optional tags |

Each option in `options`:

| Field | Type | Required | Notes |
|---|---|---|---|
| `text` | `str` | Yes | Display text |
| `value` | `int` or `str` | Yes | Stored value |
| `correct` | `bool` | No | For QUIZ strategy — marks the correct answer |
| `uuid` | `str` | No | Written by `content_save` |

### Multiple-choice question example

```yaml
---
question: "What is a variable?"
type: multiple_choice
options:
  - text: "A named container for a value"
    value: a
    correct: true
  - text: "A fixed constant"
    value: b
  - text: "A function parameter"
    value: c
```

### Short-text question example

```yaml
---
question: "What did you find most useful about this course?"
type: short_text
required: false
category: general
```

---

## FORM_CONTENT (subsequent sections with a `content` key)

The parser selects `FORM_CONTENT` when a subsequent section contains a `content` key instead of a `question` key. Used to embed explanatory markdown text between questions.

### Fields

| Field | Type | Required |
|---|---|---|
| `content` | `str` | Yes |
| `uuid` | `str` | No |

### Example

```yaml
---
content: |
  ## Reading comprehension

  Read the following passage before answering the questions below.

  > "The goal of education is not to fill a bucket but to light a fire."
```

---

## Full page YAML file example

```yaml
---
content_type: FORM_PAGE
title: Module 1 Quiz
description: Answer all questions to complete the module.
---
question: "What does a variable store?"
type: multiple_choice
options:
  - text: "A value that can change"
    value: a
    correct: true
  - text: "A fixed program instruction"
    value: b
---
content: |
  Great job! Now let's test your understanding of data types.
---
question: "Which type holds whole numbers in Python?"
type: multiple_choice
options:
  - text: "int"
    value: int
    correct: true
  - text: "float"
    value: float
  - text: "str"
    value: str
```
