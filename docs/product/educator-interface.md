# Educator Interface

_Last updated: 2026-10-11_

## Summary

- Educators use a single-page HTMX panel with three sections: Cohorts, Learners, and Courses.
- A learner or cohort can be previewed in a read-only quick-view drawer without leaving the list.
- The interface is scoped to one organisation at a time, chosen with a switcher and carried in the URL. See [Organisation Scope](#organisation-scope).
- Educators can create, edit, deactivate and delete cohorts, and register a cohort for courses or unregister it. A cohort's page shows an overview with per-course completion, then Learners, Courses and Settings tabs. See [Cohorts](#cohorts).
- The Courses list shows each course's visibility and an interest count. Visibility is read-only here.
- **Access is granted by role** — site admin, organisation admin, cohort admin or cohort viewer. Cohorts, Learners and Courses are all scoped to the current organisation and filtered to what the educator's roles cover. See [Access Control](#access-control).
- **Limits:** cohort membership, individual course registration, deadline management, and generating a cohort progress report are done in the Django admin. There is no messaging capability. See [Limits](#limits).

## Panel Interface

![Educator panel](screenshots/educator_panel.png)

The educator interface is a single-page application, scoped to one organisation at a time — see [Organisation Scope](#organisation-scope). Navigation within it is HTMX-driven: selecting a section or item updates the main panel, sidebar, and breadcrumb without a full page reload.

**Quick view.** Clicking a learner's or cohort's name opens a read-only summary in a drawer beside the list, with a link through to the full page. On a wide screen the drawer docks beside the page, and on a phone it opens as a sheet. For a learner it shows email, status, cohorts, course registrations with progress, and when they were last active in a course. For a cohort it shows status, learner count and courses. It shows only what the educator could already see on the full page. Courses have no quick view.

![Learner quick view open beside the Learners list](screenshots/educator_learner_quick_view.png)

Creating, editing, deactivating and deleting a cohort, and registering or unregistering it for a course, happen in a dialog over the current page rather than on a separate page.

### Cohorts

![Cohort page on its Overview tab, with per-course completion and the cohort's educators](screenshots/educator_cohort_overview.png)

- **List view** — each cohort in the current organisation the educator has access to, with its status, learner count and registered courses. Inactive cohorts are hidden until **Show inactive** is switched on, and the list can be filtered by course.
- **Creating and renaming** — a name is all a cohort needs, and names must be unique within an organisation. **Save and add another** keeps the dialog open for creating several in a row. An active cohort is renamed from its page header.
- **Detail page** — four tabs. *Overview* shows the cohort's details, completion for each course it is registered for, the educators assigned to it with their roles, and a needs-attention card. *Learners* lists the members. *Courses* lists the cohort's course registrations. *Settings* holds deactivation and deletion. Only a cohort the educator has access to can be opened — see [Access Control](#access-control).
- **Registering for courses** — the Courses tab registers the cohort for any course that is not coming soon, and unregisters it from a row. Unregistering is reversible and everyone keeps their progress. The confirmation says how many members lose access and names the members who keep it through another registration.
- **Deactivating** — an inactive cohort's registrations grant no access to their courses and the cohort becomes read-only; learners keep their place and progress, and reactivating restores access. See [learner tracking](./learner-tracking.md#what-is-recorded).
- **Deleting** — only while the cohort has no learners and no course registrations, removed learners and inactive registrations included; otherwise the Settings tab says what still depends on it.

Renaming, deactivating, reactivating and deleting need an organisation admin or site admin; a cohort admin can register and unregister courses on their own cohort. Not built: adding or removing cohort members (see [Limits](#limits)), bulk actions, and assigning a cohort's educators. The needs-attention card is a placeholder that always reads "Nothing needs attention yet."

### Learners

![Educator Learners list, including a learner who is not yet enrolled in anything](screenshots/educator_learners_list.png)

Lists the learners of the current organisation the educator has access to — members of cohorts they can see, plus, for an educator holding an organisation-wide role, everyone associated with the organisation, whether or not they have enrolled in anything yet. Someone studying with more than one organisation appears once per organisation, showing only the cohort memberships and course registrations belonging to the one currently in view. Learners marked removed do not appear, and there is no filter to show them. Detail pages carry the same access check as the listing; see [Access Control](#access-control).

### Courses

![Educator courses list showing each course's visibility, hidden courses included](screenshots/educator_course_visibility.png)

The Courses section is read-only and scoped to the current organisation. It lists every published course, plus any course registered to a cohort or learner the educator can see, so a hidden or coming-soon course appears only where this organisation uses it. Cohorts are registered for courses from the cohort page.

Each course shows its **visibility** — published, coming soon, or hidden — its active learner and cohort counts, and the cohorts registered for it. Counts and cohort links include only what the educator can see, and inactive cohorts are not counted. Visibility filtering only ever applies to learners, never to educator or admin views.

Each course also shows an **interest count**: the number of learners who have expressed interest through the coming-soon waitlist, counted site-wide rather than per organisation. The count is shown for every course, so a course that has since launched still shows the demand it attracted. Who expressed that interest, and when, is read in the Django admin — see [admin interface](./admin-interface.md).

The course detail view shows the title and category, the cohorts registered for the course with each cohort's status, and any direct non-cohort registrations, limited to what the educator can see. A course outside the organisation's scope returns "not found".

Visibility is **read-only** here and in the Django admin. It is set solely in the course's content frontmatter and takes effect on import — see [content editing workflow](./content-editing-workflow.md). The learner-facing experience of coming-soon and hidden courses is covered in [learner experience](./learner-experience.md).

## Organisation Scope

The educator interface is scoped to one **organisation** at a time — a grouping layer within a site, sitting above cohorts and course registrations. See [multi-tenancy and isolation](./multi-tenancy-and-isolation.md#organisations) for what an organisation is and where the isolation boundary actually sits, and [admin interface](./admin-interface.md#organisation-management) for how organisations are created.

The current organisation is part of every page's URL rather than being remembered in the session, so two browser tabs can sit on two different organisations at once, the back button behaves correctly, and any page can be linked to directly.

A switcher at the top of the left sidebar always names the current organisation. Where an educator can reach more than one, the name opens a list to switch between them; where they can reach only one, the name is still shown, as static text.

![Organisation switcher open in the educator sidebar](screenshots/educator_organisation_switcher.png)

Switching on a list page reloads it for the newly selected organisation. Switching while viewing a cohort or learner that does not belong to the newly selected organisation returns to the equivalent list with an inline notice rather than an error page.

## Access Control

Access to the educator interface and to cohort reports comes from **role assignments**. Permissions granted on a cohort or organisation in the Django admin have no effect here. There are four built-in roles:

- **Site admin** — everything, in every organisation on the site.
- **Organisation admin** — everything in one organisation, including who else administers it.
- **Cohort admin** — manages who is in a cohort and what it is registered for; cannot rename or delete it.
- **Cohort viewer** — sees a cohort and its reports; changes nothing.

These describe what each role is allowed; several of those actions have no screen in this interface yet — see [Limits](#limits). A person holding several roles gets all of them. A role on an organisation covers every cohort in it, including ones created later; a role on a cohort covers that cohort and its learners. Organisation and cohort roles count only while the person is an active member of that organisation: deactivating membership switches off their access there without deleting their roles, and reactivating restores it. Organisation admins can assign roles only within their own organisation, nobody can change their own roles, and an organisation's last admin can be removed only by a site admin.

**Not yet built.** There is no screen, in this interface or the Django admin, for assigning roles or deactivating a member; both are currently done by a developer.

**What is enforced.** The Cohorts, Learners and Courses listings are scoped to the selected organisation and filtered to what the educator's roles cover. Their detail pages carry the same check: an educator who navigates directly to one outside their access gets a "not found" response, the same response a record that does not exist would give, so identifiers cannot be probed by guessing URLs. Every write is checked before it runs, and a control the educator's role does not allow is hidden rather than shown disabled.

If an educator acts from a page that was open when their access was removed, a dialog says the action can no longer be used there and names who to ask: the organisation's admins by name where the educator may see the organisation's members, otherwise "an administrator". It offers close only, never retry. If the object itself has left their access, the dialog says it is no longer available.

**Site isolation is unaffected.** All educator interface queries remain scoped to the current site, so nothing here crosses a tenant boundary. See [multi-tenancy and isolation](./multi-tenancy-and-isolation.md).

## Limits

These operations are not available in the educator interface:

- **Cohort membership** — adding or removing learners.
- **Learner roster** — associating a person with an organisation, or marking one removed, is done in the [Django admin](./admin-interface.md#learner-rosters).
- **Individual course registration** — registering a single learner for a course.
- **Deadlines** — cohort deadlines, per-learner deadlines, and overrides.
- **Cohort progress reports** — generating a cohort's [progress report](./reports.md) is done from the Django admin. An educator with access to the cohort can have one produced, but not from this interface.

**There is no messaging capability.** Educators cannot send messages or emails to learners from FLS.
