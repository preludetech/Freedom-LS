# Research: UX patterns for authoring section links

Audience: a course author editing YAML/markdown and reading load/validation errors. No learner UI. Sources are the repo
only (`claude_plugins/fls-content` docs, `freedom_ls/content_engine/validate.py`, `content_save.py`); nothing web-sourced.

## 1. Authoring syntax: follow what exists

1. **Path, relative to the declaring file, to the content file itself.** This is the one reference idiom authors already
   use: `children:` `path:`, `access_config.application_form` ("relative to this `course.md`"), widget `path=` ("relative
   to this file and must end in the target's file name"). Code: `resolve_author_path(declaring_file, author_path)` in
   `validate.py`. The new key should reuse it. A part is named by its `part.yaml`, a topic by its `content.md`, exactly as
   in `children:` (`../shared/Core Concepts/part.yaml`).
2. **Relative base differs by where the key sits, and it is the same directory for both.** The form-level key is in
   `form.md`; the per-question key is in a page YAML in the same form directory. So `../01. intro/content.md` reads
   identically in both places. State in the docs that the base is the file holding the key. This keeps the default and the
   override copy-pasteable between each other.
3. **Name the key for what it holds, plural, always a list.** Several sections are allowed, so use one list key
   (for example `sections:`), never a scalar that sometimes becomes a list. Existing list keys (`children`, `categories`,
   `organisations`, `tags`) are plural lists. Do not accept a bare string as shorthand: a second spelling doubles the docs
   and the error cases.
4. **Entry shape.** `children:` entries are mappings (`- path: ...`) because they carry extras. If section entries carry
   nothing else, a plain list of path strings is simpler; the cost is that adding a per-entry field later (a weight, say) is
   a breaking schema change. Spec should pick one and say why. Lean: plain strings, since nothing else is in scope
   (idea.md out-of-scope: scoring and pass marks belong to spec 2).
5. **No `uuid` in the authored link.** Authors never hand-write or edit uuids (`validate-content` auto-fix rule: "never
   write or edit a uuid"; `course-files.md`: "NEVER EDIT existing UUIDs"). The path is the authored handle; the loader
   stores the resolved FK. Consequence to document: renaming or moving the target file breaks the path, and the author
   fixes the path (this is the same behaviour as `children:` today). The docs should say so in one sentence, because the
   research brief flagged "survives a rename" as open; with path-authoring the honest answer is "the stored link survives
   only if the path still resolves at the next load".

## 2. Default plus override: semantics authors will guess wrong

Today's precedent for inherit-with-override is due dates: form file default, `children:` entry replaces it for one
placement, `no_due_date: true` removes it, "an entry with neither keeps the value from the child's own file". Authors have
met this idea; reuse the vocabulary. Points the spec must pin down:

- **Override replaces, it does not merge.** A question's `sections:` replaces the form default entirely. Merge is the
  common surprise ("I added one section and still got the default ones"). Say "replaces" in the docs, with an example.
- **How a question opts out of the default.** Needs an explicit empty form, `sections: []`, meaning "tests no section".
  Distinguish from key absent (inherit). The due-date analogue is `no_due_date: true`, which exists precisely because
  absent and cleared must differ. `[]` is cheaper than a new flag and reads clearly; `sections: null` would be a second
  spelling, reject it. Pydantic must keep `model_fields_set` so absent and `[]` are distinguishable (the loader already
  relies on `model_fields_set` for `price`, see `content_save.py` line 593).
- **Storage is resolved, not inherited at read time.** Cheapest to explain: each question's stored links are its
  effective links after the load. Then a later edit that removes the form default and leaves questions bare is visible as
  removed links on next load (same "deleting the key removes it on next load" rule documented for `time_limit_days`). Spec
  must say whether removing a key removes stored links; the due-date and `price` precedents differ (`price` omitted
  leaves stored value untouched; `time_limit_days` omitted clears). For a link, "file is the source of truth, omitted
  clears" is the only rule that survives a reload without stale rows. Recommend it and document it.
- **`when` is not allowed in QUIZ forms** and section links are aimed at quizzes, but nothing says the key is QUIZ-only.
  Spec should state whether `sections:` on an `UNSCORED` or `CATEGORY_VALUE_SUM` form is allowed or an error. Precedent:
  `quiz_show_incorrect` "must be absent" for non-QUIZ strategies, and `when` is refused outside non-QUIZ. Either is
  consistent; silently accepting-and-ignoring is the one pattern the project has rejected ("a free course naming a form is
  refused rather than quietly ignored").

## 3. Error-message pattern for a broken reference

Two shapes exist today; the spec should choose the first for validation and match the second for the load:

1. **Validator block** (`_reference_error` / `_category_reference_error` in `validate.py`):
   ```
   ❌ <Header> in <file>
   Content type: <type>

     • Field: <field>
       Problem: <what is wrong>
       Given value: '<value as written>'

       <Fix: one sentence>
   ```
   Fields: header, file, content type, field, problem, the value as the author wrote it, a fix line. Category errors add a
   list of declared candidates ("Candidates"). The `when` errors likewise list the valid slugs and values.
2. **Loader error** (`content_save.py`): one line, e.g. `Course 'X' names application_form <path>, which is not a loaded
   FORM` and `Collection 'X' names a child at <path> that was not loaded`. These name the owner and the resolved path
   but give no fix and no candidates.

What a good error for this feature must carry (all three would change the spec's acceptance criteria):

- **Locate the question, not just the file.** Page YAMLs hold many questions as `---` sections with no ids. The user
  answered "naming the question and the missing target". The only handles an author recognises are the file name, the
  question text (truncate to ~60 chars) and its 1-based position in the file, plus the `slug` when one is set. The
  `uuid` is useless to an author. For the form-level key, name `form.md` and the field `sections[<n>]` (precedent:
  `Field: categories[0]`).
- **Show the path as written and as resolved.** `Given value: '../01. intro/content.md'` plus the resolved repo-relative
  path. The relative-to-declaring-file base is the main source of off-by-one `../` mistakes, and the author cannot see the
  resolved path otherwise.
- **Distinguish the failure causes in `Problem:`.** (a) no file at this path; (b) file exists but is not a COURSE_PART or
  TOPIC (e.g. `this file is a FORM, not a COURSE_PART or TOPIC`; precedent: widget check "this file is a X, not an
  ARTICLE"); (c) file exists but was not part of this load run (the `application_form` "not a loaded FORM" case, which
  matters when `content_save` is run on a subset); (d) the same section listed twice (precedent: "each child is named
  once"). Case (b) matters because a quiz author's likely slip is pointing at a `form.md` or a `course.md`.
- **Offer nearest candidates for case (a).** Existing practice is to list the valid set; a content repo can have hundreds
  of topics, so list only the siblings of the resolved parent directory, or the closest by name, not all of them. This is a
  suggestion, not a precedent; the spec can drop it.
- **Collect, do not stop at the first.** The validator returns a list of error blocks (`errors: list[str]`); the loader
  currently raises one `ValueError` at the first problem in most places, but joins placement errors
  (`"\n".join(placement_errors)`, `content_save.py` line 975). An author fixing a form with five bad paths wants all five
  in one run. Recommend the section-link check collect across the whole load before raising.
- **Fail the whole load, before any write.** "Error at load" is settled; the spec should add that the check runs before
  rows are written so a half-loaded form is not left behind. A reference check must live in a binding pass after all
  content is parsed (a quiz can name a topic that is loaded later in the same run), like the `application_form` pass.

## 4. Where the two tools disagree today, and what to say

- `/fls-content:validate-content` is **offline** and its closing note says it does not do "cross-reference resolution".
  But `validate.py` already does resolve references offline (widget paths, `children:`, categories, `when`). The
  `validate-content` note text is stale on this point. If the section link is resolved offline (and it can be: pure path
  lookup in the parsed file set), the note should be corrected rather than left saying the opposite. Whether the offline
  check can see "target lives outside the validated directory" depends on the directory validated: validating one form
  directory alone cannot resolve `../01. intro/content.md`. Precedent: `validate.py` line 721 parses un-passed files "on
  first use" from disk. The spec should say whether a path outside the validated set that exists on disk and parses
  counts as resolved (recommended, matching that line) so authors validating a single folder do not get false errors.
- An unplaced "bank form" has no course to resolve against, but paths resolve against the declaring file, not a course, so
  this causes no extra authoring difference. Worth a docs sentence: the section path does not depend on the form being
  placed.

## 5. Docs the author needs (small, concrete)

- `form-files.md`: add the key to the FORM table (form-level default) and the FORM_QUESTION table (override), one example
  of each, one example of `sections: []`, one worked error. Put the rules next to the `when` rules in the same style
  (bullets: base path, replaces-not-merges, empty list, must be a COURSE_PART or TOPIC, duplicates, QUIZ-only or not).
- The key's name must not collide in the author's mind with `COURSE_PART`/"section" vocabulary: the domain term is
  "course part" and "topic"; "section" is the idea's word. Keep the key `sections` only if the docs define it once as
  "a course part or a topic". If the spec prefers the domain terms, a `tests:` or `covers:` key reads as an action and
  avoids the word. Spec decision, not a research one.
- `validate-content.md`: correct the closing "does not perform cross-reference resolution" note, and add a step-4 example
  of translating the new error into plain language.

## 6. Smaller points that would change the spec

- **Auto-fix boundary.** `validate-content` may auto-fix "an unknown field that is plainly a misspelling" (`section:` for
  `sections:`). A mistyped *path* is not auto-fixable (author judgement); say so, otherwise the formatter agent may guess a
  target.
- **content-formatter / `format-content`** rewrite files; confirm they preserve a new unknown-to-them key and list order
  (a `sections:` list reordered would change nothing semantically, but a dropped key would silently remove links).
- **Quoting.** Paths with spaces and numbered prefixes (`01. intro`) are valid unquoted YAML scalars; a path starting with
  `..` is also fine. No quoting rule needed, but a path containing `: ` or ` #` would break it; the existing docs already
  say "quote the value" in the `when` section, so one line in the new section is enough.
- **Order.** The list order has no meaning. Say so, or the author will wonder whether the first section is "primary" (the
  revision feature's "point a wrong answer back to the section" could then be ambiguous with several; that is spec 3's
  concern, but the authoring doc should not imply a primary).

status: ok
