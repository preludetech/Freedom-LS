# Deadline Feature — Frontend QA Results

## Summary

All tests **PASSED** (with one test skipped due to missing test data). No bugs found.

---

## Test Results

| Test | Description | Result |
|------|-------------|--------|
| 1a | CohortDeadline via inline | PASS |
| 1b | CohortDeadline standalone | PASS |
| 1c | StudentDeadline via inline | PASS |
| 1d | StudentCohortDeadlineOverride | PASS |
| 2a | Hard deadline (future) - red display | PASS |
| 2b | Soft deadline (future) - orange display | PASS |
| 2c | Multiple deadlines | PASS |
| 2d | CoursePart deadline | SKIPPED |
| 3a | Item-level hard deadline expired, item NOT completed | PASS |
| 3b | Item-level hard deadline expired, item completed | PASS |
| 3c | Course-level hard deadline expired | PASS |
| 3d | Soft deadline expired | PASS |
| 3e | Direct URL access to locked item | PASS |
| 4a | Override beats cohort deadline | PASS |
| 4b | Item-level beats course-level | PASS |

---

## Skipped Tests

### Test 2d: CoursePart deadline
- **Reason:** The test course "Functionality Demo - show end with Topic" does not contain any CoursePart objects. This test requires a course with CourseParts to verify that deadlines display on CoursePart rows rather than individual items.
- **Recommendation:** Create a test course with CourseParts, or add a CoursePart to the existing course, then re-run this specific test.

---

## Notes

### Test 4a: Override student mismatch
During Test 4a, the StudentCohortDeadlineOverride was initially created for student `demodev_s1` (via the admin inline), but the QA tests were being run as user `demodev@email.com` (a different Student record). The override had to be reassigned to the correct student via Django shell to verify the override behavior. This is not a bug — it's a test setup issue. The admin correctly enforces that override students must be cohort members, and both students were valid cohort members.

### Test 4b: No incomplete items besides Pictures
For Test 4b, the course-level deadline was set to the past. However, all items except Pictures were already completed. Since completed items are never locked (verified in Test 3b/3c), only Pictures demonstrated the item-level-beats-course-level behavior. The core priority logic is correct: Pictures with an item-level override (future) remained accessible despite the expired course-level deadline.

---

## Screenshots

| File | Description |
|------|-------------|
| `screenshots/test1a_cohort_deadline_inlines.png` | CohortCourseRegistration with Deadlines and Student Deadline Overrides inlines |
| `screenshots/test1a_course_level_deadline_saved.png` | After saving a course-level deadline |
| `screenshots/test1b_standalone_list_with_filters.png` | CohortDeadline standalone list with filters panel |
| `screenshots/test1c_student_deadline_inline.png` | StudentCourseRegistration with Deadlines inline |
| `screenshots/test1d_student_override_saved.png` | After saving StudentCohortDeadlineOverride |
| `screenshots/test2a_toc_deadlines_display.png` | Full TOC with all deadline badges visible |
| `screenshots/test3b_completed_item_expired_deadline_accessible.png` | Completed item with expired hard deadline still accessible |
| `screenshots/test3c_course_level_expired_hard_deadline.png` | Course-level expired hard deadline effects |
| `screenshots/test4a_override_beats_cohort_deadline.png` | Override (future) overrides cohort deadline (past) |
| `screenshots/test4b_item_level_beats_course_level.png` | Item-level override beats expired course-level deadline |
