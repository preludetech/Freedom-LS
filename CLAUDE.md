# Project: Freedom Learning System (FLS)

This is a fully functioning Learner Management System. 

It is designed to be installed into other Django projects. FLS will work out of the box, but is designed to be extended and customized.

## Stack

Python 3.13+, Django 5.x, PostgreSQL 17, HTMX 2.x, django-template-partials, TailwindCSS

Use modern Python syntax: `X | None` instead of `Optional[X]`, `list[str]` instead of `List[str]`, etc.

## Commands

- `uv add PACKAGE` - install package
- `uv run python manage.py runserver` — dev server
- `uv run pytest` — run tests
- `uv run manage.py makemigrations` - make migrations
- `uv run manage.py migrate` - migrate
- `npm run tailwind_build` Build tailwind 

## Key directories

- `freedom_ls/` — Django applications
- `demo_content/` — Course content demonstrating all course functionality
- `config/` — settings and root URLconf

## App Structure (`freedom_ls/`)

- `accounts` — Custom site-aware user model with email-based login
- `app_authentication` — API client authentication and key management
- `base` — Base app configuration
- `content_engine` — Course content models (topics, forms, activities) with markdown rendering
- `educator_interface` — Educator views for managing cohorts and viewing student progress
- `site_aware_models` — Base models and manager for multi-site support with automatic site filtering
- `student_interface` — Student views for browsing courses, tracking progress, completing content
- `student_management` — Student profiles, cohorts, course registrations, recommendations
- `student_progress` — Progress tracking for topics, forms, and courses with scoring strategies

## Conventions

- We use a custom site-aware user model `AUTH_USER_MODEL = "accounts.User"`
- Type hints required on all functions. No `Any`.
- Never hardcode credentials. All credentials come from environmental variables unless they are only for use in development
- ORM only: no raw(), extra(), or RawSQL without security review.
- HTMX CSRF: set globally via `<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>`
- Use select_related()/prefetch_related() for all related-object queries.
- Return HTTP 422 for HTMX validation errors. See `docs/templates_and_cotton.md` for full HTMX conventions.
- Always run `uv run manage.py makemigrations` after model changes, then `uv run manage.py migrate`
- Never edit existing migration files — create new migrations instead
- Avoid repeating code. If there is code being repeated then favor extracting it into a new function/class and calling it as needed
- Don't build functionality that is not explicitly requested
- When catching exceptions, be specific about the types of exceptions being handled. Avoid silent failures
- Don't add `# type: ignore` comments
- Don't create abstract base classes unless asked
- Don't add logging unless asked
- Prefer `get_object_or_404` over manual try/except for view lookups
- Every app must define `app_name` in its `urls.py`
- URL names use snake_case (e.g., `name="cohort_detail"`)
- URL paths use kebab-case (e.g., `"cohorts/detail"`)

## Testing

Follow the testing skill and refer to `docs/testing.md` for all testing conventions and TDD workflow.

## Important: Use skills

Whenever you are asked to do anything, use all the appropriate skills. Rely on skills rather than pre-training.
