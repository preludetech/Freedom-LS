# QA data conventions for FreedomLS

`sdd:qa-data-helper` reads this file before it creates, resets or deletes development data. Paths below are from the project root.

## Factories first

Create data with factory_boy factories. `claude_plugins/fls-dev/resources/factory_boy.md` holds the project's factory conventions, including the `SiteAwareFactory` base. Search `tests/`, each app's `factories.py`, `conftest.py` files and the `qa_helpers` app for an existing factory before writing a new one. A new factory goes in the app that owns the model.

## The `qa_helpers` app

Scripts, management commands and helper utilities for QA data go in the `qa_helpers` app, with commands in `qa_helpers/management/commands/`. A `qa_helpers` command carries no test unless it deletes data. A test for a deleting command carries the `dev_tooling` marker.

## Site-aware data

Every record belongs to a Site, so give created data the site the tester browses. Site-aware managers do not filter outside a request, so a plain `Model.objects.filter(...)` in `manage.py shell` sees every site. Print each record's site when locating records to delete.

## Ways to create data

1. A management command, for a scenario that will be wanted again: `uv run python manage.py <command_name>`.
2. A one-off script: `uv run python manage.py shell -c "<script>"`, or `uv run python manage.py shell < script.py`.
3. A management command with arguments, for quantities and specific attributes.

## What the report carries

- Credentials for every created user: email and a simple password such as `testpass123`.
- Names of the courses, cohorts and other entities created.
- Counts of each entity.
- Relationships: which users are in which cohorts, registered on which courses.
- The URL paths where the data shows, when you can determine them.
