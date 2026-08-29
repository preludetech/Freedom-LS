# Admin Interface

_Last updated: 2026-08-29_

## Summary

- The Django admin is enhanced with the Unfold UI framework, preserving all standard Django admin behaviour.
- Administrators grant educators access to specific cohorts through per-object permissions.
- Organisations are created, renamed, and given a logo — optionally a second, reversed one for a dark background — entirely through the admin, with no delete and no merge. Assigning someone a staff role on an organisation grants access to every cohort inside it, including ones added later.
- An organisation's learners are curated in the admin and only there: an administrator associates a user with an organisation before or independently of any enrolment, and marks a learner removed. Removal is soft — it suspends that person's access to the organisation's courses without touching their memberships, registrations, or progress — and a learner cannot be deleted outright.
- A course registration that has recorded progress cannot be deleted, and nor can a cohort whose registrations have. Deactivating a registration or removing a cohort member withdraws access without touching the progress.
- Authored content — courses, course parts, topics, activities, files, and forms — cannot be deleted through the admin at all, inlines included. Adding and changing stay available.
- A staff user generates a cohort's progress report from the admin by picking a cohort and triggering generation; the choice is limited to cohorts that user is allowed to see, generation runs in the background, and the finished PDF downloads through a permission-checked link rather than a public URL.
- The admin path is configurable via `DJANGO_ADMIN_URL`, so production can move it off the default location.
- Legal consent records are fully read-only — they cannot be added, changed, or deleted.
- Webhook endpoints have a test-send action for verifying configuration without waiting for a real event.

## Unfold

The admin uses [Unfold](https://github.com/unfoldadmin/django-unfold) as a drop-in enhancement over Django's standard admin. It provides an improved layout while leaving standard admin behaviour intact.

Site-scoped admin pages are automatically filtered to the current site, consistent with [multi-tenancy and isolation](./multi-tenancy-and-isolation.md). Unfold's branding customisation (site title, header colour, logo) is present in settings but commented out, so admin branding is not configured in a default installation.

## Cohort Permissions

Each cohort's admin detail page carries a permissions tab, where an administrator grants an individual educator view access to that one cohort. The educator interface honours those grants: its cohort and learner listings, and their detail pages, show only what the educator has been given — the [known gap](./educator-interface.md#access-control) has narrowed to the Courses section, which remains unguarded. Per-cohort grants and [organisation staff roles](#organisation-management) are two independent routes to the same access, at different granularity.

## Organisation Management

Organisations are managed entirely through the Django admin: an administrator creates an organisation, renames it, uploads a logo, and assigns staff to it. An organisation can also supply a second, reversed logo for use on a strong colour fill; both are optional, and today only the first is drawn anywhere. What an organisation is, and where it sits relative to a site, is described in [multi-tenancy and isolation](./multi-tenancy-and-isolation.md#organisations).

There is no delete and no merge — both are refused outright. This is a deliberate limit for this release, not an oversight. There is also no bulk import, and no way to manage organisations outside the admin.

Assigning someone a staff role on an organisation, through the same per-object permissions tab used for cohorts, grants them access to every cohort in that organisation in the educator interface, including cohorts added later. It is the alternative to granting per-cohort permissions one at a time. See [educator interface](./educator-interface.md#organisation-scope) for how educators move between the organisations they can reach.

Logo uploads accept PNG, JPEG, and WebP; SVG is rejected deliberately. A maximum file size and minimum and maximum pixel dimensions apply, and each upload is validated against its actual image bytes rather than trusted by filename — see [security and data handling](./security-and-data-handling.md).

## Learner Rosters

An organisation's roster — who belongs to it, independently of any enrolment — is curated in the Django admin, and only there; the educator interface's [Learners section](./educator-interface.md#learners) is read-only. An administrator associates an existing user with an organisation as one of its learners, and the same person can be a learner of more than one organisation on a site. See [multi-tenancy and isolation](./multi-tenancy-and-isolation.md#organisations) for what an organisation is.

Removing a learner is soft: it suspends their access to courses held through that organisation, but never deletes or alters their cohort memberships, course registrations, or progress history, and leaves their standing in any other organisation untouched. Reactivating them restores access with nothing to rebuild. A learner cannot be deleted outright.

The same restraint extends to course registrations: once a registration has recorded [progress](./learner-tracking.md), the admin refuses to delete it and lists the progress standing in the way. Deleting a cohort cascades to its registrations, so that delete is blocked too, and a course cannot be deleted here at all. Deactivating a registration, removing a cohort member, or marking a learner removed all stay available and leave the recorded progress intact.

There is no bulk add or remove, no CSV import, and no view showing one person's associations across every organisation at once.

## Course Interest

Who has expressed interest in each course is read here, searchable by user and course. Interest is expressed against a course site-wide with no organisation involved, which is why it sits in the admin rather than in the organisation-scoped [educator interface](./educator-interface.md#courses), where only the per-course interest count is shown.

## Cohort Progress Reports

A staff user generates a cohort's progress report from the admin: they pick a cohort from a dropdown and trigger generation with one click. The dropdown only ever offers cohorts that user is allowed to see — a per-cohort grant or an [organisation staff role](#organisation-management), the same two routes described under [cohort permissions](#cohort-permissions) — so a cohort outside both is never offered, and a request naming one anyway is refused. What the finished report contains is described in [cohort reports](./reports.md).

![](screenshots/admin_generated_reports.png)

- Generation runs in the background: the report appears in the list right away and updates once it finishes, either becoming available to download or showing a readable explanation of why it failed. Starting a second report for a cohort that already has one generating is refused with a message; a finished or failed report never blocks a new one.
- The finished PDF is fetched through a permission-checked download link in the list, never a public media URL. See [security and data handling](./security-and-data-handling.md) for the access posture behind that link.
- Reports are produced by the system, not authored by hand: they cannot be added or edited from the admin, only viewed, downloaded, and deleted. Deleting a report also deletes its stored PDF.
- Cohort names are unique per organisation rather than per site, so both the list and the generation dropdown name each cohort's organisation alongside the cohort.

## Configurable Admin URL

The admin is mounted at the path given by the `DJANGO_ADMIN_URL` environment variable. Changing it in production moves the admin off its default location, reducing exposure to automated discovery. No code change is required.

## Read-Only Consent Records

Legal consent records are registered read-only: the admin disables add, change, and delete. This preserves the append-only integrity of the consent audit trail, described in [authentication](./authentication.md).

## Content Cannot Be Deleted

Authored content — courses, course parts, topics, activities, files, and forms with their pages, questions, and options — cannot be deleted through the admin: not from a detail page, not as a bulk action, and not from an inline on a parent. Adding and changing remain available, and content is authored in files and loaded into the site by a command, so the admin is not where content is removed. See [content editing workflow](./content-editing-workflow.md).

Underneath the admin the same protection holds for anything reaching the database another way: a form question a learner has answered, and a course anyone is registered for, cannot be deleted while those records exist.

## Webhook Test-Send

A webhook endpoint's admin detail page exposes an action that sends a test payload to the configured URL, so an administrator can confirm the endpoint is reachable and its authentication headers are correct before a live event triggers delivery. The full control set is in [webhooks](./webhooks.md).
