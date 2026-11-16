# Idea: general lead capture forms

## What

A site-aware way to capture marketing leads: enquiry, "talk to us" and callback forms on public
pages. Each submission is stored once, along with the form it came from, its answers and the
visitor's first-touch attribution. Staff get an email for each new lead, and leads can be exported to
CSV. Each form is defined by configuration (its fields, topics and contact methods), not by code
written separately for every form.

## Why

FLS captures interest in a course (`course_interest`) and course applications, but has nothing for a
general enquiry that isn't about a single course. Concrete projects that run landing pages need this.
First-Class-LMS built a complete version: a model, form variants, a notification email task, deploy
checks for a missing recipient or from-address, and a CSV export that is safe against formula
injection. Those pieces are generic, and the next project would build the same thing again.

## Reference implementation

First-Class-LMS (`/home/sheena/workspace/first_class/First-Class-LMS.git/main`):

- `apps/lead_forms/`: models, forms, services, emails, tasks, checks, config, variants, form config
  and middleware
- `apps/admin_dashboard/lead_csv.py`: the export's column table

Some parts of it are specific to that project and stay there: its topic choices (drone-industry
slugs), company sizes, the SAST column in the CSV, and its contact-method options. In FLS these
become per-project configuration. The scan read the models, checks and tasks, but not the forms,
services, variants or views in detail. Check those for project data before relying on them.

## Settled

- First-touch attribution comes from `referral_tracking`, the same source signups use.
- The project keeps its own form definitions as configuration and deletes the generic code once FLS
  ships it.

## Open

- Whether this is a new app or an extension of `course_interest`.
