# Project: Freedom Learning System (FLS)

This is a fully functioning Learner Management System. 

It is designed to be installed into other Django projects. FLS will work out of the box, but is designed to be extended and customized.

## Stack

Django 5.x, PostgreSQL 17, HTMX 2.x, django-template-partials, TailwindCSS

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

## Conventions

- We use a custom site-aware user model `AUTH_USER_MODEL = "accounts.User"`
- Type hints required on all functions. No `Any`.
- Never hardcode credentials. All credentials come from environmental variables unless they are only for use in development
- ORM only: no raw(), extra(), or RawSQL without security review.
- HTMX CSRF: set globally via `<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>`
- Use select_related()/prefetch_related() for all related-object queries.
- Return HTTP 422 for HTMX validation errors.
- Avoid repeating code. If there is code being repeated then favor extracting it into a new function/class and calling it as needed
- Don't build functionality that is not explicitly requested
- When catching exceptions, be specific about the types of exceptions being handled. Avoid silent failures

## Detailed documentation

When you do work related to one of the following, be sure to read and apply the documentation.

- @docs/multi_tenant for understanding site isolation, SiteAwareModel and use of Django Sites framework
- @docs/frontend_styling.md to see how Tailwind is used to style frontend components
- @docs/testing.md for test conventions
- @docs/templates_and_cotton.md for Django templates and cotton components


