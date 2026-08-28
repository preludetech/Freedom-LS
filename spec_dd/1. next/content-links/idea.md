# Content links: make `<c-content-link>` produce a working URL

> **Split out of** `better_course_progress_tracking`. Its QA runs surfaced two
> defects in the `<c-content-link>` cotton component. We are not using content
> links in any live course yet, so the fix was deferred here rather than done
> inside a progress-tracking branch.

## The need

`<c-content-link path="...">text</c-content-link>` lets an author link from one
piece of course content to another by file path. The lookup half works. The URL
half does not: a link that resolves to a Form renders a dead anchor, and a link
that resolves to a Topic 500s. So the component cannot be used in real content
today.

## The two defects

**A Form link renders `<a href="">`.** `content-link.html:12` emits
`{{ content_obj.preview_url }}`, but `Form` (`freedom_ls/form_engine/models.py:43`)
has no `preview_url` method, so the attribute resolves to empty. The anchor is
clickable and goes nowhere. Recorded as a known non-finding in QA plan
`3c. form_engine_regression_qa` §0.4 of the parent spec.

**A Topic link raises `NoReverseMatch`.** `Topic.preview_url()`
(`freedom_ls/content_engine/models/topics.py:18`) reverses
`content_engine:topic_detail`. No URLconf defines that name. Every `topic_detail`
route is commented out at `freedom_ls/learner_interface/urls.py:52-62`, and the
name is namespaced to `content_engine`, which has no learner-facing URLs at all.
Any link that resolves to a Topic will 500 the page it sits on.

This one is latent rather than observed, and only by luck: the three
`<c-content-link>` instances in `demo_content/` all point at
`01-what-is-git-for.md`, which no Topic anywhere has as its file path, so they
take the not-found branch and render the error span. Fix the dangling demo paths
and the 500 appears.

## The design question this really turns on

There is no such thing as a standalone URL for a Topic or a Form in FLS today.
Learners reach content through a course, by position:
`courses/<course_slug>/<index>/` (`view_course_item`). That route enforces course
access, deadlines and item locking. The commented-out `topic_detail` and
`form_detail` routes are the old slug-based, course-free way in, and reviving
them would route around all of that.

So `preview_url()` is asking the wrong question. A content object cannot say
where it lives without knowing which course, and which registration, the reader
is in. Resolve during the spec:

- Should a content link render as a `view_course_item` URL for the course the
  reader is currently in, and what happens when the target is not an item in
  that course?
- What does the link do when the reader has not unlocked the target, or the
  target sits behind a deadline? Rendering a link they cannot follow is worse
  than rendering plain text.
- Is `preview_url` an educator or author preview concept that got reused for
  learners? The `TODO. - non-preview link` in `content-link.html:5` suggests the
  author who wrote it knew these were two different needs. Leave that TODO in
  place until the work is done.

## Also in scope

- The second half of the same TODO: leading and trailing whitespace around the
  rendered anchor (`content-link.html:12` emits `{{ slot }} ` with a trailing
  space).
- The dangling `01-what-is-git-for.md` demo paths in
  `demo_content/functionality_demo_end_with_quiz/2. topic/content.md`,
  `.../4. topic/content.md` and
  `demo_content/functionality_demo_end_with_topic/1. topic/content.md`. Point
  them at content that exists, so a resolvable Topic link is exercised in demo
  content the way `test_demo_content_form_link.py` already guards the Form link.

## Reference material

- Component: `freedom_ls/content_engine/templates/cotton/content-link.html`
- Lookup filter: `get_content_by_path`,
  `freedom_ls/content_engine/templatetags/content_tags.py:147`, with unit
  coverage in `freedom_ls/content_engine/tests/test_content_tags.py`
- Working Form link in demo content:
  `demo_content/functionality_demo_end_with_quiz/2. topic/content.md:55`,
  guarded by `freedom_ls/content_engine/tests/test_demo_content_form_link.py`
- The live item route: `view_course_item`, `freedom_ls/learner_interface/urls.py:21`
