## Project Overview

This is a multi-site Learning Management System (LMS) built with Django. The project uses a site-aware architecture where all models are scoped to Django Sites, enabling multiple independent LMS instances to run from a single codebase.

## Code style

Import statements should go at the top of the file 

### Exception handling

- Try blocks hould be as short as possible
- When catching exceptions, be specific about the types of exceptions being handled. Avoid silent failures

## Development Environment

### Package Management
- **uv** is used for Python dependency management
- Install dependencies: `uv sync`
- Activate virtual environment: `source .venv/bin/activate`

### Running the Server
```bash
python manage.py runserver
```

### Frontend/Styling
- Uses TailwindCSS v4
- Build CSS: `npm run tailwind_build`
- Watch CSS during development: `npm run tailwind_watch`
- **IMPORTANT**: `tailwind.input.css` contains reusable component classes (buttons, forms, etc.)
  - **ALWAYS check `tailwind.input.css` FIRST** before writing any inline Tailwind classes for common UI elements
  - **USE existing component classes** when they exist (e.g., `.btn`, `.btn-primary` for buttons)
  - Only write inline Tailwind classes for truly unique, one-off styling that doesn't match existing components
  - Add new component classes to `tailwind.input.css` if creating something reusable that doesn't exist yet
  - Keep things DRY - don't duplicate styles that already exist in the component library

### Database
- Apply migrations: `python manage.py migrate`
- Create migrations: `python manage.py makemigrations`

### Testing
- Pytest is used for testing (via pytest-django)
- Settings configured in `pyproject.toml`
- Default test settings module: `config.settings_dev`
- Shared fixtures are in `conftest.py` at project root
- when creating tests, make one test at a time
- Run specific test: `pytest path/to/test_file.py::test_name`

To run all tests except for the tests of the bloom app run `pytest`

To run the Bloom tests in isolation, run `pytest concrete_apps/bloom_student_interface --ds concrete_apps.bloom_student_interface.config.settings_dev`

To run all the tests (including the Bloom tests) run: `pytest apps concrete_apps/bloom_student_interface --ds concrete_apps.bloom_student_interface.config.settings_dev`





## Architecture

### Django app location 

All apps are inside the `apps/` directory. This is on the PATH. 

When importing something from an app in the `apps` directory:

```
# DONT DO THIS
from apps.content_engine.models import Course

# Rather, leave out the `apps` part of the import statement. This works
from content_engine.models import Course
```

### Site-Aware Models Pattern
The core architectural pattern is site isolation using Django Sites framework:

- **SiteAwareModelBase**: Adds a ForeignKey to Django Site and includes SiteAwareManager
- **SiteAwareModel**: Extends SiteAwareModelBase with UUID primary key
- **CurrentSiteMiddleware**: Stores the current request in thread-local storage (`_thread_locals.request`)
- All models automatically filter by current site via the manager's `get_queryset()`
- On save, models auto-populate `site_id` from thread-local request if not set

This means most queries automatically scope to the current site based on the request's domain.

### Custom User Model
- `AUTH_USER_MODEL = "accounts.User"`
- User model extends AbstractBaseUser and is site-aware
- Uses email-based authentication (no username field)
- UserManager also filters by site

### Multi-Tenancy Configuration
- Site-specific configuration in `config/settings_base.py` via `site_conf` dict
- Each site can have custom branding (SITE_TITLE, SITE_HEADER, COLORS)
- Unfold admin interface uses `get_unfold_value()` to dynamically load site-specific settings

### Django Apps Structure

**Core Apps:**
- `accounts`: Custom User model with email-based auth
- `site_aware_models`: Base models, managers, and middleware for multi-site support
- `student_management`: Student, Cohort, and CourseRegistration models
- `content_engine`: Content models (Topic, Form, Collection) with markdown rendering
- `student_interface`: Student-facing views, APIs, and progress tracking
- `app_authentication`: Authentication-related functionality

**Framework Apps:**
- Uses django-allauth with headless mode for API authentication
- django-unfold for admin interface customization
- django-guardian for object-level permissions
- django-cotton for component-based templates
- template-partials for partial template rendering
- django-ninja for REST API

### Content Engine
- Content types: Topic, Form, Collection, FormPage, FormQuestion, FormContent
- Base classes: `BaseContent`, `TitledContent`, `MarkdownContent`
- Markdown rendering with custom tags (c-youtube, c-picture, c-callout, c-content-link)
- Content files stored with relative `file_path` to content root
- `calculate_path_from_root()` method converts relative paths between content items

### Student Registration System
Students can be registered for courses in two ways:
1. **Direct registration**: StudentCourseRegistration links Student to ContentCollection
2. **Cohort-based registration**: Students join Cohorts, Cohorts register for courses
3. `Student.get_course_registrations()` merges both registration types

### API Structure
- Main API defined in `config/urls.py` using django-ninja's `NinjaAPI()`
- Student API: `/api/student/` (routed to `student_interface.apis.router`)
- Uses allauth headless authentication (`x_session_token_auth`)
- Authentication via `_allauth/` endpoints

### Template System
- Uses django-cotton for component-based templates
- django-template-partials for HTMX-style partial rendering
- Custom template loaders with caching enabled
- Template builtins include cotton and partials templatetags

## Settings
- `config/settings_base.py`: Base settings for all environments
- `config/settings_dev.py`: Development settings (DEBUG=True, debug toolbar)
- Settings module specified in pyproject.toml for pytest

## Important Patterns

### Testing with Site-Aware Models
Use the `mock_site_context` fixture from `conftest.py` when testing models that require site context:
```python
def test_something(mock_site_context):
    # Models will automatically use the mocked site
```

### Markdown Content
Content models that extend `MarkdownContent` can access rendered HTML via `rendered_content()` method, which processes custom tags defined in `MARKDOWN_ALLOWED_TAGS`.

### Fixtures
Common fixtures in `conftest.py`:
- `site`: Creates a test Site
- `user`: Creates a test User
- `form`: Creates a test Form
- `make_temp_file`: Helper for creating temporary files
- `mock_site_context`: Mocks site context for SiteAwareModel

## Development Notes

- DEBUG toolbar is enabled in development but disabled during tests
- Browser reload middleware enabled for development
- Media files served in development mode at `/media/`
- Static files at `/static/`
