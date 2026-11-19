# QA diff scoping

Classify a diff's changed paths into one class; the first matching rule decides.

## Rule 1: front-end paths

Any changed path that contains `templates/` or `static/`, or ends in `.html`, `.css` or `.js`,
makes the class `FULL`.

## Rule 2: admin only

If every changed path is `admin.py` or inside an `admin/` directory, the class is `ADMIN_ONLY`.

## Rule 3: Python only

If every changed path ends in `.py`, the class is `BACKEND_ONLY`.

## Rule 4: everything else

Anything else is `FULL`.

## What each class runs

- `FULL`: desktop, mobile and tablet.
- `ADMIN_ONLY`: desktop only.
- `BACKEND_ONLY`: desktop only, abbreviated to the cases that exercise the changed server-side code.
