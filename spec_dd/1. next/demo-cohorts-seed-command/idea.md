# Idea: a demo cohorts seed command

## What

A management command that fills a site with demo cohorts for showing off cohort-shaped features. It
creates a chosen number of cohorts, each holding a chosen number of deterministic demo learners with
verified email addresses, in the site's organisation. Running it again changes nothing, because names
and emails come from the cohort and learner index. The site is picked by name or domain, so it works
with a forced site name as well as a host-based one.

## Why

FLS has `qa_create_*` scenario commands for QA walks and `setup_initial_prod_data` for a production
bootstrap, but nothing that gives a host project's dev server a handful of believable cohorts to
demo the educator interface or the cohort pages against. Every concrete project that demos FLS needs
this, and First-Class-LMS already wrote one. It has no project name, brand or data in it.

## Reference implementation

First-Class-LMS (`/home/sheena/workspace/first_class/First-Class-LMS.git/main`):

- `apps/project_setup/management/commands/setup_demo_cohorts.py`

It has no tests in the project. Two things are project-shaped and become options in FLS: the
hard-coded dev-site domain (`127.0.0.1:8000`) and the `demo_..._@email.com` address template. Demo
learners' passwords equal their email address, which is acceptable only for disposable dev data; the
FLS version should keep the command out of production use the way the other dev-only commands do.

The project would delete its copy once FLS ships the command.

## Settled

- It belongs with FLS's own dev and demo commands, under an `fls_`-style name, not in a project.
- It only adds data. It never deletes or resets existing cohorts or learners.
