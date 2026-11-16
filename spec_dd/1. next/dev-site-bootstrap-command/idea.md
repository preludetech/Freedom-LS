# Idea: a command that bootstraps the local dev site

## What

A development-only management command that makes the local dev Site ready to use in one step. It
creates the Site named by `FORCE_SITE_NAME` on the local dev host, or renames the existing one, and
refuses when another Site already holds that name. It also creates a dev superuser whose email address
is already verified, so the first login on a fresh database works without an email round trip.

## Why

Every concrete project that runs with `FORCE_SITE_NAME` needs a Site under that name before anything
else works. Until one exists, FLS's site lookup and its seed and QA commands have nothing to attach to.
FLS has `create_demo_data`, which builds its own demo Site, and `setup_initial_prod_data`, which is for
production, but nothing for a project's own dev Site. Projects end up writing the same few steps
themselves, and the duplicate-name check is easy to leave out. Without it, two Sites can share the
forced name and the lookup picks one at random.

## Reference implementation

First-Class-LMS (`/home/sheena/workspace/first_class/First-Class-LMS.git/main`):

- `apps/project_setup/management/commands/make_dev_site.py`
- `apps/project_setup/tests/test_make_dev_site.py`

It uses only FLS models and settings. The dev credentials are development-only constants.

## Settled

- Development only. Production keeps using `setup_initial_prod_data`.
- The command lives in FLS's `dev_tools` app.
- The project deletes its copy once the FLS command exists.
- This sits next to `forced-site-name-for-host-based-site-lookup`, which covers serving that Site on
  any dev port. This idea covers creating the Site in the first place.
