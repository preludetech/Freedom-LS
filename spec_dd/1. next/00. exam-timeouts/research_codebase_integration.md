# Form Time Limits: Codebase Integration Research

## Overview
This document maps the existing form infrastructure in FLS to identify the minimal change footprint needed to add form-level time limits with server-authoritative deadline tracking.

---

## 1. Form Model Definition

**Location:** `/freedom_ls/content_engine/models.py:249-273`

### Current Structure
```python
class Form(TitledContent, MarkdownContent):
    CONTENT_TYPE = SchemaContentTypes.FORM

    strategy = models.CharField(
        max_length=50,
        choices=FormStrategy.choices,  # CATEGORY_VALUE_SUM, QUIZ
    )
    quiz_show_incorrect = models.BooleanField(blank=True, null=True)
    quiz_pass_percentage = models.PositiveSmallIntegerField(blank=True, null=True)
```

### Strategy Field
- `FormStrategy` enum at line 24 defines two strategies:
  - `CATEGORY_VALUE_SUM`: sums numerical values by category (used for assessments)
  - `QUIZ`: calculates pass/fail based on correct answers
- Strategy determines how scoring is calculated (not submission behavior)
- No existing time-based configuration on the Form model

### Where to Add Time Limit
The `Form` model is the correct place to add `time_limit_minutes` field (e.g., optional `PositiveIntegerField`).

---

## 2. Form-Attempt Progress Tracking

**Location:** `/freedom_ls/student_progress/models.py:123-162`

### FormProgress Model
```python
class FormProgress(CourseItemProgress):
    form = models.ForeignKey(Form, ...)
    user = models.ForeignKey(User, ...)
    start_time = models.DateTimeField(auto_now_add=True)  # Line 135
    last_updated_time = models.DateTimeField(auto_now=True)  # Line 136
    completed_time = models.DateTimeField(blank=True, null=True)  # Line 137
    scores = models.JSONField(blank=True, null=True)
```

### Timestamps Tracking
- **`start_time`** (auto_now_add): When the attempt was first created (set once)
- **`completed_time`**: Set to `timezone.now()` when `.complete()` is called (line 268)
- **`last_updated_time`**: Auto-updated on every save
- No deadline tracking field yet

### Server-Authoritative Deadline
Add new field to FormProgress:
- `deadline = models.DateTimeField(blank=True, null=True)` — calculated at attempt start as `start_time + form.time_limit_minutes`
- Server validates submission against this deadline before accepting answers

---

## 3. Form Submission Flow

**Location:** `/freedom_ls/student_interface/views.py:250-413`

### Three Views Handle Forms

#### 3a. view_form (lines 250-286)
- **Purpose**: Render form intro page with start/resume/retry buttons
- **Input**: Form, course, index
- **Gets existing progress**: `FormProgress.get_latest_incomplete(user, form)`
- **Output**: Renders `course_form.html` template

#### 3b. form_start (lines 289-309)
- **Purpose**: Initialize or resume a form attempt
- **Creates/gets FormProgress**: `FormProgress.get_or_create_incomplete(user, form)` (line 298)
- **Determines current page**: `form_progress.get_current_page_number()` (line 301)
- **Action**: Redirects to `form_fill_page` with the current page number

#### 3c. form_fill_page (lines 312-413)
- **Purpose**: Render individual form pages and accept answer submissions
- **On POST (lines 344-358)**:
  - Saves answers: `form_progress.save_answers(questions, request.POST)` (line 346)
  - If more pages exist: redirect to next page
  - If last page: calls `form_progress.complete()` and redirects to results page

### Submission Strategy: Page-by-Page
- Submission is **not one-shot** — each page is submitted individually
- User progresses through pages with Next/Back buttons
- **No auto-save between pages** (answers only saved on form POST)
- When last page is submitted, `complete()` is called which:
  - Sets `completed_time = timezone.now()`
  - Calculates final `scores` via strategy-specific scoring method
  - Saves to DB

**Key insight:** There is no explicit "submit form" button; completing the last page auto-finalizes.

---

## 4. Auto-Save / Partial Submission Mechanics

**Current State**: None detected.

- Answers are saved only on explicit form submission (POST)
- No AJAX auto-save between pages
- No draft state tracking
- `last_updated_time` auto-field tracks when any change was made, but not intelligently

### For Time Limits
- Page-by-page submission is natural; deadline check can happen on each page POST
- No conflicting auto-save logic to integrate around
- Could optionally add JavaScript countdown timer on client (display only; server is authoritative)

---

## 5. Single Form Model vs. Multiple Form-Like Things

**Finding**: Single canonical `Form` model represents a form.

Hierarchy:
- **Course** (container for learning units)
  - Children can include: **Form**, **Topic**, **Activity**, **CoursePart**
  - Forms are just another content type in a course
- **Form** (the actual form with scoring)
  - Has many **FormPage** instances (ordered by `order` field, line 282)
  - Each FormPage has many **FormQuestion** and **FormContent** children
- **FormPage** (lines 276-302)
- **FormQuestion** (lines 323-369)
  - Has many **QuestionOption** (lines 372-387)

### Where time_limit_minutes Should Live
- **`Form` model** is the correct place
- All pages and questions within a form share the same time limit
- Time limit applies to the entire attempt, not individual pages

---

## 6. Content Schema & Management Command

**Schema Location**: `/freedom_ls/content_engine/schema.py:126-166`

### Form Schema (Pydantic Model)
```python
class Form(BaseContentModel, MarkdownContentModel, content_type=ContentType.FORM):
    strategy: FormStrategy = Field(..., description="Strategy for form scoring")
    quiz_show_incorrect: bool | None = Field(None, ...)
    quiz_pass_percentage: int | None = Field(None, ...)

    @model_validator(mode="after")
    def validate_quiz_fields(self):
        # Ensures quiz_show_incorrect and quiz_pass_percentage are set
        # only when strategy is QUIZ
        ...
```

### Adding time_limit_minutes to Schema
Add to Form schema at line ~142:
```python
time_limit_minutes: int | None = Field(
    None,
    description="Optional time limit in minutes for completing the form"
)
```

### Management Command: content_save

**Location**: `/freedom_ls/content_engine/management/commands/content_save.py`

#### How It Works
1. **Parses YAML/frontmatter** via `parse_single_file()` (validates against Pydantic schemas)
2. **Generic save function** `save_with_uuid()` (lines 224-302):
   - Extracts all Pydantic model fields
   - Maps to Django model fields
   - Validates field names match model
   - Auto-generates slug from title
   - Creates or updates with UUID

3. **Form-specific save** `save_form()` (lines 364-366):
   ```python
   def save_form(item, site, base_path):
       return save_with_uuid(Form, item, site, base_path)
   ```
   - Directly maps Pydantic `Form` to Django `Form` model
   - Any new field in schema automatically picked up by `save_with_uuid()`

#### Integration
- Once `time_limit_minutes` is added to the Pydantic schema, it's automatically saved to the Django model
- **No changes needed to `content_save.py`** — schema validation and mapping are generic

### Example Markdown Content Structure (Future)
```yaml
---
content_type: FORM
title: Assessment Quiz
strategy: QUIZ
quiz_show_incorrect: true
quiz_pass_percentage: 70
time_limit_minutes: 30
---

Form introduction text...
```

---

## 7. Client-Side Interactivity: Alpine.js & HTMX

**Alpine.js Location**: `/freedom_ls/student_interface/static/student_interface/js/alpine-components.js`

### Current Usage
- Alpine used minimally: only for course-part expand/collapse (`coursePart` data component, lines 10-34)
- Data binding: `x-data="coursePart"`, `x-show`, `x-on:click`
- Mainly for local UI state; no async operations

### HTMX Usage
**Location**: `/freedom_ls/student_interface/templates/student_interface/_course_base.html`

Minimal HTMX usage detected:
- `hx-get` for loading course table of contents on page load
- `hx-trigger="load"`
- `hx-indicator` for loading spinner

### For Time Limits
**Do NOT need complex client-side state management:**
- Form submission remains traditional POST (current behavior)
- Display-only countdown timer can be added with Alpine or vanilla JS
- Timer is informational only; server enforces the actual deadline

**Possible enhancement** (optional):
- Add Alpine component to display countdown on form page
- Read deadline from context variable passed by view
- Client-side countdown for UX; server is authoritative on deadline enforcement

---

## 8. Summary: Minimal Footprint for Time Limits

### Changes Required

#### A. Data Models
1. **Form model** (`freedom_ls/content_engine/models.py`):
   - Add `time_limit_minutes = models.PositiveIntegerField(blank=True, null=True)`
   - Migration needed

2. **FormProgress model** (`freedom_ls/student_progress/models.py`):
   - Add `deadline = models.DateTimeField(blank=True, null=True)`
   - Migration needed

#### B. Content Schema
1. **Form Pydantic schema** (`freedom_ls/content_engine/schema.py`):
   - Add `time_limit_minutes: int | None = Field(None, ...)`
   - No code changes to content_save.py required

#### C. Views
1. **form_start view** (`freedom_ls/student_interface/views.py:289-309`):
   - When creating FormProgress, calculate and set `deadline = start_time + form.time_limit_minutes`

2. **form_fill_page view** (`freedom_ls/student_interface/views.py:312-413`):
   - Before saving answers (line 346) or on page render:
     - Check if `current_time > form_progress.deadline`
     - If exceeded: redirect to completion page with "time exceeded" message
   - Pass `deadline` to template context for optional countdown display

#### D. Templates
1. **course_form_page.html** (optional):
   - Display countdown timer (if deadline is set)
   - Or just pass deadline to JavaScript for client-side display

### Server-Authoritative Enforcement
- Server validates deadline on every form submission (page POST)
- Client-side timer is UX only; server makes final decision
- **No client-side submission bypass possible**

### Where Time Limit Does NOT Apply
- Time limit is **per attempt**, not per page
- Once `form_progress.deadline` is set at attempt start, it applies to all pages
- If student skips pages and comes back, original deadline is still enforced

---

## File Dependencies Summary

| Component | File | Key Lines | Purpose |
|-----------|------|-----------|---------|
| Form model | `content_engine/models.py` | 249-273 | Add `time_limit_minutes` field |
| FormProgress model | `student_progress/models.py` | 123-162 | Add `deadline` field |
| Form schema | `content_engine/schema.py` | 126-166 | Add `time_limit_minutes` to Pydantic schema |
| Submission views | `student_interface/views.py` | 250-413 | Enforce deadline on form_start and form_fill_page |
| Form page template | `student_interface/templates/course_form_page.html` | 1-190 | Optional: display countdown timer |
| Content save command | `content_engine/management/commands/content_save.py` | 224-366 | No changes needed (generic schema mapping) |

---

## Key Decisions for Spec

1. **Time limit location**: On `Form` model (applies to entire attempt, not per-page)
2. **Deadline storage**: On `FormProgress` record (calculated at attempt start as `start_time + form.time_limit_minutes`)
3. **Enforcement point**: Both at `form_start` (prevent resumption after deadline) and `form_fill_page` (prevent submission after deadline)
4. **Submission model**: Remains page-by-page (no change to UX flow)
5. **Client-side timer**: Optional enhancement for UX; server is authoritative
6. **Backcompat**: `time_limit_minutes` is optional (NULL = no limit), existing forms unaffected

---

## Open Questions for Spec

1. Should a form with a time limit allow resumption *after* the deadline expires? (E.g., view completed submission but not retake?)
2. Should there be a "soft" deadline (warning) vs. "hard" deadline (block)? (Current research assumes hard deadline.)
3. Should failed quiz retries reset the deadline or inherit the original?
4. Should there be a grace period or immediate cutoff?
