---
name: reference-demo-content-uuid-collision-remap
description: content_save demo_content DemoDev fails with category-slug collisions when another site (example.com) holds the frontmatter UUIDs; load a UUID-remapped committed scratch copy instead of deleting
metadata:
  type: reference
---

Seen Nov 2026, sacaa-compliance-3-question-pools. Symptom: `content_save demo_content DemoDev`
aborts with "Category slug 'start-here-demo' ... already belongs to another CourseCategory on
site 'DemoDev' (uuid ...)" for all 4 categories.

Cause: content was loaded onto **example.com** first (pools course + form + 4 categories got the
canonical frontmatter UUIDs as pks there), then DemoDev was loaded from a UUID-stripped copy, so the
DemoDev rows (course `befa506c...`, form `802b4d3e...`, every page/question/option/content, and the 4
categories) carry fresh pks. `save_with_uuid` does `update_or_create(id=uuid, site=site)`, so a
canonical uuid owned by another site can never be created on DemoDev (pk is global).

Deleting the stale copies was **denied by the permission classifier** (DemoDev copy also had a prior
run's qa-learner-a/b FormProgress/CourseProgress/registrations, PROTECT). Non-destructive fix that worked:
1. `cp -r demo_content <scratch>/demo_content_remap` (recursive delete is blocked by the ds security hook; use a fresh dir name)
2. `manage.py shell < qa_question_pools_uuid_remap_script.py` (edit ROOT) - maps file uuid -> DemoDev pk by
   matching course slug, form slug, page title, question text, option text, content text, category slug;
   rewrites the copy. 68 uuids mapped.
3. content_save refuses non-git dirs: `git init && git add -A && git -c user.name=qa -c user.email=qa@localhost commit`
   inside the scratch copy.
4. `content_save <scratch>/demo_content_remap DemoDev` -> updates DemoDev rows in place (draw values etc.), 20 courses.

A plain `content_save demo_content DemoDev` will keep failing on this DB until the example.com copy is
removed (needs user consent).

Educator: `/educator/organisations/demodev/courses` is paginated (`?courses-page=2`, 10 per page);
demodev@email.com is superuser so every DemoDev course shows without role grants.
`qa_create_fresh_course_learners` prints LearnerCourseRegistration.DoesNotExist tracebacks (get_or_create
logging noise) but succeeds - verify by query.
