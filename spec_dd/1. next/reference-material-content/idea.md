> This idea has been cut into 4 specs. Their order, dependencies, the decisions already taken and
> the assumptions are in the "Reference material" section of `spec_dd/1. next/roadmap.md`. Start there.
> The text below is the original brief and is kept as written.

In some courses we'll have reference material and cheatsheets that can be accessed at any time.

For example, in a concrete implementation we are doing some drone training. We will want to have the relevant regulations available to learners doing the course. They wont need to read these regulations in detail, just refer back to them as needed.

We might also have "courses" that are actually just libraries of reference material.

The reference material should be visible in the educator interface like other content.

## Data structures

Reference material sits beside a course's learning path, not inside it.

### Keep reference material out of `Course.items`

`Course.items` (the `ContentCollectionItem` rows whose collection is the course) is the learning path. Around 160 non-test call sites walk it through `viewable_items()`, `collection_items()`, `viewable_collection_items()` and `children()`, and treat every child as part of that path. Reference parts placed there, or flagged on `ContentCollectionItem`, would:

- count toward completion, `progress_percentage` and `lesson_count`
- shift the flat position in `courses/<slug>/<int:index>/` and fall under progression gating
- be offered due dates by the deadline resolver, the outline and overrides

So `Course.items` stays as it is.

### Reuse `CoursePart` and `Topic`, add one through model

```
Course ──items──────────────► ContentCollectionItem ─► CoursePart / Topic / Form   (learning path, unchanged)
   │
   └──reference_parts──► CourseReferencePart(course, course_part, order)           (new)
                                   │
                                   ▼
                              CoursePart ──items──► ContentCollectionItem ─► Topic  (reused as is)
```

- `CourseReferencePart` (new): a `SiteAwareModel` with a `course` FK, a `course_part` FK and an `order`, unique on `(course, course_part)`. It is the only new table.
- A reference part is an ordinary `CoursePart` whose children are `Topic` rows placed through `ContentCollectionItem`. Rendering, slugs, the admin and the content loader work unchanged.
- Nesting is one level: reference part → topics. Deeper nesting (e.g. regulation Part → Subpart → Section) comes later, and may need a collection model of its own at that point. Out of scope for the first version, but not dropped.

### Authoring

`course.md` gets a `reference:` key that mirrors `children:`:

```
main_course_dir/
    course.md
    1_part/
       part.yaml
       topics and things
    2_part/ ...

    reference/
        1. regulations/
            part.yaml
            topics
```

```yaml
children: [...]
reference:
  - path: reference/1. regulations/part.yaml
  - path: ../shared_drone_regs/part.yaml   # shared across courses
```

Paths can reach outside the course directory, as `functionality_demo_course_parts_placement` does, so one set of regulations can be written once and attached to several courses.

Validation rejects:

- due keys (`due_date`, `due_time`, `due_days_after_registration`, `no_due_date`) on a reference entry or inside a reference part
- `Form` children in a reference part: reference parts hold topics only
- a part that is both in a course's learning path and in that course's reference list

### Library-only courses

A library is a `Course` with an empty learning path and only reference parts. It reuses registration, visibility, owning organisations, course shares, the catalogue and pricing, so access needs no new model. The learner side has to handle a course with no children: progress percentage, the finish page, the resume pointer and the course home layout.

## Behaviour

- Learners reach reference topics at their own URLs, e.g. `courses/<slug>/reference/<part_slug>/<topic_slug>/`, with access checked by `is_registered_for_course`. The course chrome has a Reference entry reachable from any position in the course.
- Viewing reference material is not tracked: no progress, no audit entry, no "last viewed".
- Reference material is markdown topics only. No PDF or `File` downloads in this version.
- The educator interface shows a Reference section in the course outline and content preview (`educator_interface/panels/course/content_preview.py`).

## Things to check

- `content_save.py`, `moved_children.py` and `danger_content_delete.py` must know about `CourseReferencePart`.
- About 16 sites query `ContentCollectionItem.objects` directly, and some deadline code assumes every part has a placement in a course. A part used only as reference has none, so those queries need checking.
