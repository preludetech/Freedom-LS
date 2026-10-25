# Research: known complaints about organisation-restricted course catalogues

Scope note: web search surfaced vendor docs and support/forum threads, not Reddit or G2/Capterra review text. No direct first-hand "duplicate same-named course" complaints were found. Items below marked (inferred) are design implications, not sourced complaints.

## Sourced findings

1. "Course missing for a user" is the dominant complaint, and is usually a mapping problem, not a bug.
   - Latitude Learning: a course is usually missing because the user's location/business unit is not on the course's Organizations list. https://support.latitudelearning.com/?p=5532
   - TalentLMS: branch catalogues are separate; course status and catalogue visibility are distinct settings, so an active course can still be hidden. https://help.talentlms.com/hc/en-us/articles/29263493515292-Why-doesn-t-a-course-show-up-in-the-TalentLMS-Course-Catalog
   - Adobe Learning Manager: learners not in the audience group do not see the catalogue at all. https://community.adobe.com/t5/adobe-learning-manager-discussions/creating-a-catalog-of-courses-and-making-it-viewable-by-certain-user-groups/m-p/12237454
   - Adobe: learners saw a program but not its component courses. https://community.adobe.com/questions-471/courses-in-learning-programs-do-not-appear-in-catalog-246847

2. Learners seeing an empty or confusing catalogue when they are not assigned.
   - Docebo: unassigned users still see the catalogue block with a "nothing there" message. https://community.docebo.com/product-q-a-7/course-catalog-visibility-7187

3. Restriction leaks through secondary surfaces (search, "Discover new", direct URL).
   - Open edX: setting catalogue visibility to none still left courses in Discover New; one user needed Invitation Only to truly hide a course. https://discuss.openedx.org/t/how-do-i-hide-a-course-from-the-discover-new-section/6806 , https://discuss.openedx.org/t/completely-hiding-a-course-from-everyone-but-a-particular-group/7651
   - Open edX: search skips the show-in-catalogue filter by default (SEARCH_SKIP_SHOW_IN_CATALOG_FILTERING = True), so "hidden" courses can appear in search. https://discuss.openedx.org/t/the-course-search-behaviour-for-courses-with-different-visibility-settings/9119
   - Open edX: group-level course visibility is a repeated feature request with no built-in answer. https://discuss.openedx.org/t/user-groups-and-courses-visibility/6585 , https://discuss.openedx.org/t/course-group-visibility/10779

4. Per-organisation separation in Open edX needs separate sites/domains (course_org_filter), so users must know which site to log into. Appsembler (Tahoe) adds Course Access Groups. https://discuss.openedx.org/t/completely-hiding-a-course-from-everyone-but-a-particular-group/7651 , https://appsembler.com/?p=12470

5. Users in multiple organisations: Moodle Workplace restricts each user to a single tenant; no personal data is shared between tenants by default; sharing is an admin opt-in; users can be moved between tenants. Platforms avoid the multi-membership problem rather than solving it. https://docs.moodle.org/en/Multi-tenancy

6. Admin burden and reporting (vendor-side, biased):
   - Traditional multi-client setups use a separate portal per customer; multi-tenancy is pitched as removing that duplication and enabling aggregated reports. https://www.commlabindia.com/blog/how-to-manage-multiple-clients-under-single-lms , https://elearningindustry.com/when-a-multi-tenant-lms-actually-makes-sense
   - Admitted trade-off: central updates may not fit individual tenants; stronger isolation makes cross-tenant reporting harder. https://www.softdecc.com/en/references/library/multi-tenancy-lms.html
   - Audience-based visibility recommended so staff only see relevant content. https://elearningindustry.com/learning-management-system-to-support-multi-tenancy-how-use

## Implications for this spec (inferred)

- Enforce restriction in every surface, not just the catalogue list: dashboard, search, course detail by direct URL, applications list, educator and admin lists, and reports. Open edX history shows leaks arise from forgotten secondary surfaces.
- Admins need a way to see why a learner does or does not see a course (organisation membership vs course organisation list). "Missing course" support tickets are the top complaint.
- Same-named per-organisation courses will be confusable in admin lists, educator views and reports; show the organisation on the card (as the idea requires) and in every list or report that names a course. (No sourced complaint; reasoning from the idea.)
- A learner in several organisations needs a defined rule for which organisation's course version they see; most platforms sidestep this by single-membership. Flag as an open question.
- Empty-state wording: avoid showing a catalogue that says "nothing here" when courses exist for other organisations.
- Reports should group or filter by organisation to avoid mixing same-named courses from different organisations.

## Gaps

No Reddit, G2 or Capterra results were obtained; the search tool returned none. Treat the above as vendor-forum evidence only.

status: ok
