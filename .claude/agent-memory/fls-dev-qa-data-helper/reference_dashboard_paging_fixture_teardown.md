---
name: reference-dashboard-paging-fixture-teardown
description: Tearing down the whole qa_create_dashboard_paging_fixtures seed (4 Pagination courses, 3 personas, demodev_s1's extra recommendations) - the delete ORDER forced by three PROTECTs, and the Topic rows nothing cascades
metadata:
  type: reference
---

Sequel to [[reference_qa_run_residue_cleanup]]: the "a previous QA run's fixtures block this
run's baseline" ask, aimed at everything
`qa_helpers/management/commands/qa_create_dashboard_paging_fixtures.py` writes
(better-learner-dashboard-course-display, Sep 2026, site DemoDev pk=3).

**Read the seeding command first.** Its module docstring lists Seeds A-E and the exact slugs /
emails, which is a faster and more complete inventory than querying model by model - it is how I
knew Seed C also completes two *demo* courses (`functionality-demo-course-parts`,
`standard-markdown-demo-finance`) whose registrations ride along with the persona delete.

## The delete order is forced by three PROTECTs

1. `RecommendedCourse` (CASCADE from both User and Course, no inbound relations) - delete first
   so the count is reportable on its own; otherwise the course delete silently eats it.
2. Personas: `CourseProgress._base_manager.filter(learner__user=u).delete()` **then** `u.delete()`.
   `User.delete()` raises `ProtectedError` naming `'Learner.user'` - misleading, because the actual
   protector is `CourseProgress.learner_registration`/`.learner` two levels down the cascade
   (User -> Learner -> LearnerCourseRegistration -> PROTECTed by CourseProgress).
3. Courses: `Course` is PROTECTed by `LearnerCourseRegistration.course`,
   `CohortCourseRegistration.course` and `CourseProgress.course`, so every persona must be gone
   first. CASCADE inbound: `CourseApplication`, `CourseInterest`, `RecommendedCourse`.
4. `Topic` last - PROTECTed by `TopicProgress.topic`.

## Course.delete() DOES take its ContentCollectionItems, but NOT the Topics

`Course` declares a `GenericRelation`, so the collector loads the `ContentCollectionItem` rows
(collection side) and the `Course_categories` m2m through-rows. Real shape for 4 one-topic courses:

```
(12, {'Course_categories': 4, 'Course': 4, 'ContentCollectionItem': 4})
```

The **child** side has no such relation, so the 4 `Topic` rows survive as orphans and must be
deleted explicitly afterwards. Guard each with
`ContentCollectionItem._base_manager.filter(child_id=t.pk).count() == 0` before deleting - a topic
reused by another course would otherwise be pulled out of that course's TOC. Here all 4 were
single-use (`pagination-<letter>-lesson-1`).

## Sizing generic references before a content delete

`ContentCollectionItem` was the *only* GenericFK holder pointing at these courses/topics - no
deadlines, no xapi rows. Worth the 20-line scan every time (walk `apps.get_models()`,
`model._meta.private_fields` for `GenericForeignKey`, filter on `ct_field`/`fk_field`), because
these references are invisible to `Collector` and to `_meta.related_objects`. Cast the pks to
`str()` in the filter - `object_id`-style columns here are char, not uuid.

## Cascade counts observed (useful as a regression baseline)

- 4 `RecommendedCourse` (demodev_s1 -> pagination-a..d); the
  `content-widgets-demo-reference` row is the *intended* seed and must survive.
- `demodev_paging`: progress `(7, {TopicProgress: 1, CourseProgress: 6})`, then user
  `(9, {LearnerCourseRegistration: 6, EmailAddress: 1, Learner: 1, User: 1})`.
- `demodev_history`: progress `(16, {TopicProgress: 10, CourseFormAttempt: 2, CourseProgress: 4})`,
  then user `(19, {QuestionAnswer_selected_options: 5, QuestionAnswer: 5,
  LearnerCourseRegistration: 4, EmailAddress: 1, FormProgress: 2, Learner: 1, User: 1})`.
  Note `FormProgress` hangs off the **User**, not the CourseProgress, so it is only counted in the
  second delete even though the sittings were course sittings.
- `demodev_empty`: `(3, {Learner: 1, EmailAddress: 1, User: 1})` - `ensure_learner` mints a
  `Learner` even for a persona with zero registrations.
- Courses `(12, ...)` as above, Topics `(4, {'Topic': 4})`.

## Gotchas

- `CourseCategory` has **`title`, not `name`** (`slug`, `subtitle`, `order`, `show_on_dashboard`).
  The verification block died on `cat.name` after the deletes had already committed - harmless
  here, but put field-name-risky *reporting* code in a separate script from the deletes.
- `Course.dashboard_category` (FK) and `Course.categories` (m2m) are set independently by the
  seeding command; deleting the courses leaves the `CourseCategory` rows at
  start-here=2 / assessment=2 / reference=1 on DemoDev, which is the clean demo-content baseline.
- DemoDev's clean course list is exactly 5 slugs: `content-widgets-demo-reference` (coming_soon),
  `functionality-demo-course-parts`, `functionality-demo-show-end-with-quiz`,
  `functionality-demo-show-end-with-topic`, `standard-markdown-demo-finance`.
- Re-seed with `qa_create_dashboard_paging_fixtures DemoDev` (idempotent, `--seeds ABCDE`); Seed E
  requires `demodev_s1@email.com` to exist already (`qa_create_rich_dashboard_learner`).
