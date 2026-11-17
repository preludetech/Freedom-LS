# Answers: educator-interface-course-list-shows-too-much

Asked by `/sdd:start` before the spec was written. The permission structure was decided against
`research_cross_org_course_sharing.md` and `research_permission_model_patterns.md`.

- Q: On an educator's Courses page, which courses should show? → A: Full access to the organisation's own courses. Another organisation's course shows only if this organisation is allowed to see it, and never with a content preview. (asked up front)
- Q: Should the same rule apply to the course pickers when an educator registers a learner or cohort for a course? → A: Yes, same rule. (asked up front)
- Q: When a cohort or learner already holds a registration for another organisation's course, should that course still show for the educator? → A: If the registration belongs to the current organisation, show it. (asked up front)
- Q: Should educators be blocked from opening another organisation's course detail page and content previews directly by URL? → A: Yes, return 404 (where no grant allows it). (asked up front)
- Q: Where are grants to other organisations declared? → A: In course.md front matter, beside `organisations:` and `audience:`. (asked up front)
- Q: Can a grant name every other organisation at once ('*'), or only named organisations? → A: Named organisations only; no wildcard. (asked up front)
- Q: With no grant, what do educators of another organisation get on a public course? → A: Hidden: not in the Courses list or course pickers, detail page 404. Its learners still self-join through the course's own gates. (asked up front)
- Q: Which rights can an owner grant another named organisation? → A: Three independent flags, `see`, `register` and `preview`; `register` and `preview` each imply `see`. Owner organisations (listed in `organisations:`) have everything; a course with no organisations keeps today's behaviour. (asked up front)
- Q: Does a `register` grant let that organisation's educators register learners directly, skipping the course's price and application gate? → A: Yes. The grant is the licence; seat caps can come in a later spec. (asked up front)
