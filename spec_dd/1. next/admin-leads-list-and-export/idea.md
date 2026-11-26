# Idea: a staff list of leads, with filters and CSV export

## What

One place where staff see everyone who has shown interest in the site, one row per person. A person
is merged by lowercased email from every source FLS knows: lead submissions, course applications,
course interest, accounts and course registrations. Staff filter the list by a date range, counted
either by any activity in the range or by when the person was first seen, and by marketing channel.
The list pages, and downloads as a CSV that is safe against formula injection.

## Why

FLS records each kind of interest in its own app, and `referral_tracking` now classifies a first
touch into a marketing channel, but nothing answers "who came to us this month, and from where?"
across all of them. Sales and marketing staff on any concrete project ask that question. First-Class-LMS
built it as an admin page and it works on FLS models alone, apart from the parts named below.

## Reference implementation

First-Class-LMS (`/home/sheena/workspace/first_class/First-Class-LMS.git/main`):

- `apps/admin_dashboard/leads.py`: the per-email merge and the date-basis filter
- `apps/admin_dashboard/forms.py`: `LeadFilterForm`
- `apps/admin_dashboard/views.py`: `LeadListView` and `lead_list_download`
- `apps/admin_dashboard/lead_csv.py`: the CSV columns
- `apps/admin_dashboard/templates/admin_dashboard/lead_list.html`
- `apps/admin_dashboard/admin.py`: `LeadProfileLinkMixin`, a permission-gated link to a person's profile
- tests beside them: `test_leads.py`, `test_forms.py`, `test_views.py`

Three parts are project-specific and do not move as they are:

- The CSV and the date filter use a hard-coded South African timezone. In FLS that is the site's
  timezone setting.
- An "intro course progress" block reads the project's landing-page constants. In FLS it is either an
  optional "tracked course" setting or left to the project as an extension.
- The `LeadSubmission` source only exists once the `lead-capture-forms` idea ships, so this idea
  comes after that one. The project also keeps its own copy of the channel classifier
  (`apps/admin_dashboard/channels.py`), which FLS now ships in `freedom_ls.referral_tracking.channels`.

The project would keep its intro-course column as an extension and delete the merge, filter form,
view and CSV plumbing.

## Settled

- It depends on `lead-capture-forms`.
- Channel classification is `freedom_ls.referral_tracking.channels`, not a new classifier.
