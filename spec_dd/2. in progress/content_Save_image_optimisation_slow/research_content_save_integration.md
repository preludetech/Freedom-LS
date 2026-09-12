# Research: what a committed `_optimised/` encode cache collides with

Scope: this is a pure codebase-reading report against the settled decisions in the task brief
(cache lives in `_optimised/` beside the source images it caches, committed to git, one
`manifest.yaml` per `_optimised/` directory, orphans deleted per run, only the encode is cached).
No design proposal, no helper-function names.

## 1. The skip rules — two independent copies, same semantics

There are exactly two scanners, and they are **not** the same code (no shared import):

- `freedom_ls/content_engine/validate.py:22-75` (`get_all_files`) — the one `content_save` and
  `content_validate` actually run against a real content repo.
- `claude_plugins/fls-content/validate/validate.py:83-136` — a bundled, hand-synced copy used by
  the author-facing offline validator plugin. Its header comment (`validate.py:1-16`) documents
  the sync process (`/update_claude_plugin_fls_content`) and lists patches applied on top of the
  core copy; the `should_skip`/`get_all_files` body itself (lines 95-136) is byte-for-byte the
  same logic as the core copy, not derived from it at runtime — a future change to one has to be
  re-applied to the other by that sync command, same as every other patch in that file's header.
  Any change to skip semantics has to land in both, or the plugin's offline validator and the real
  loader disagree about what counts as content.

There is also a **third**, narrower copy of half the rule: `is_skipped_path` in
`content_save.py:566-572`, used only by `save_content_to_db`'s child-auto-discovery walk (the
branch that runs when a `course.md`/`part.yaml` omits `children:`). Its docstring says explicitly
it "mirrors the filtering rules in `get_all_files`". This is a third place a directory-naming
convention has to hold.

Precise semantics, quoted from `get_all_files`'s `should_skip` (`content_engine/validate.py:47-48,
50-60`):

```python
# Skip files starting with _ or .
if file_path.name.startswith("_") or file_path.name.startswith("."):
    return True

# Skip files in directories starting with _ or . (only check parents within base_path)
try:
    relative_path = file_path.relative_to(base_path)
    for parent in relative_path.parents:
        if (
            parent.name
            and parent.name != "."
            and (parent.name.startswith("_") or parent.name.startswith("."))
        ):
            return True
except ValueError:
    pass
```

This is a **file**-level filter applied via `path.rglob("*")` (`validate.py:70-73`): `rglob`
descends into every directory including `_optimised/` (Python's `rglob` does not itself refuse to
recurse into a dot/underscore directory), and each file found under it is then rejected because one
of its `relative_path.parents` starts with `_`. The directory entry itself is never yielded by
`rglob("*")` filtered to `f.is_file()`, so `_optimised/` as a directory is simply never inspected —
what is skipped is every *file* inside it, one by one, via the parent-name check. Net effect is the
same as "skip the directory and everything under it," but mechanically it is a per-file skip, not a
`os.walk`-style prune. `is_skipped_path` in `content_save.py` differs: it is applied to a single
`Path` (a direct child of `collection_dir.iterdir()` or `item.iterdir()`), checking only
`path.name` — so a directory named `_optimised` is skipped at the point that directory itself is
listed as a candidate child, before anything inside it is ever touched (`content_save.py:915,
934-942`).

Conclusion for the cache: as long as the cache directory is literally named `_optimised` (leading
underscore, not e.g. `.optimised` — both would work by this rule, but the brief already settles on
`_optimised`), all three scanners already skip it and everything under it, with no code change
needed to any of the three copies. The hazard is only that this depends on the *existing* skip
convention continuing to hold — the cache's placement is not enforced by any new code path, it
free-rides on a convention that already has three independent copies to keep in sync.

## 2. What `save_file_to_db` needs from a cache hit

Flow today, `content_save.py:650-736`:

1. `relative_path = str(file_path.relative_to(base_path))` — the `File.file_path` key.
2. `file_type = get_file_type_from_extension(file_path)` and a `mimetypes.guess_type` guess —
   **both computed from the path/suffix alone, no file read**.
3. If `file_type == File.FileType.IMAGE`: `raw = file_path.read_bytes()` (the **only** place the
   source bytes are read), then `decision = optimise_image(raw, file_path.suffix)`,
   `before_bytes = len(raw)`. If `decision.data is not None`, `mime_type = decision.mime_type`
   (`"image/webp"`) overwrites the guessed mime type.
4. `File.objects.get_or_create(...)` / metadata update on the existing row, using `file_type`,
   `file_path.name` as `original_filename`, and `mime_type`.
5. `stored_name` is `file_path.with_suffix(decision.suffix).name` when `decision.data is not None`,
   else `file_path.name`. `encoded = ContentFile(decision.data)` or `None`.
6. Superseded-storage-object handling (`:695-713`, discussed in §7).
7. `file_obj.file.save(stored_name, encoded, save=True)` — the only DB write in the function,
   commits `file_type`/`mime_type`/the file field together.
8. Two author-facing `click.echo` lines built entirely from the returned `ImageEncodeDecision`
   (`_format_image_decision_line`, `_format_bytes`) plus `before_bytes`/`len(decision.data)` — see
   §3 for what those need.

**What a cache has to supply to leave this path's behaviour unchanged:** exactly the fields of
`ImageEncodeDecision` (`images.py:29-53`) — `status`, `data` (the stored bytes or `None`),
`suffix`, `mime_type`, `lossless`, `stored_size`, `source_format`, `source_size`, `error`. Nothing
else reaches `save_file_to_db`'s DB write or storage write. If a cache hit reconstructs (or stores
verbatim) an `ImageEncodeDecision`, the rest of the function — the `File` upsert, the superseded-key
dance, `file_obj.file.save(...)`, and both echo lines — runs completely unchanged, since all of it
already treats `decision` as an opaque value regardless of how it was produced.

**What the source read is still needed for, and what a hit avoids.** `file_path.read_bytes()`
(`:661`) currently serves two purposes at once: it is the input to `optimise_image`, and
`before_bytes = len(raw)` feeds the "before -> after" byte-count line (`:725-731`,
`_format_bytes(before_bytes)`). A cache keyed on a digest of the source bytes has to compute that
digest from *something* — either the same `read_bytes()` (in which case the read is not avoided,
only the ~420ms *encode* is, since hashing bytes already in memory is comparatively free next to a
Pillow decode/resize/WebP-encode), or from a cheaper proxy such as mtime/size recorded in
`manifest.yaml` (in which case the read can be skipped on a hit, but then the cache is trusting
filesystem metadata rather than content, which is weaker against e.g. a git checkout that resets
mtimes). Either way: **a cache hit unambiguously avoids the Pillow decode + resize + WebP encode
(the ~420ms cost named in the brief) and the `mimetypes.guess_type` override logic tied to it**; it
does **not** avoid `File.objects.get_or_create`, the metadata-update branch, the superseded-object
bookkeeping, or `file_obj.file.save(...)` — those still run once per file, every run, cache or no
cache, because they are DB/storage operations with no cache layer proposed for them (confirmed by
the settled decision "nothing about how files are uploaded to `course_media` storage changes"). If
the digest strategy chosen ends up requiring `raw` regardless (content-hash rather than
mtime/size), the *disk read* itself is not saved either — only the CPU-bound encode is.

## 3. The run summary

Aggregation is in `save_content_to_db` (`content_save.py:750-764, 1011-1016`): `image_statuses` is
a plain `list[ImageEncodeStatus]`, one entry appended per image file (`decision.status`, from
whatever `save_file_to_db` returned — nothing else populates it). At the end:

```python
counts = Counter(image_statuses)
per_status = ", ".join(
    f"{counts[status]} {status}" for status in ImageEncodeStatus if status in counts
)
summary = f"Images: {len(image_statuses)} seen"
click.echo(f"{summary} ({per_status})." if per_status else f"{summary}.")
```

`ImageEncodeStatus` (`images.py:22-26`) is a closed, four-member `StrEnum`
(`OPTIMISED`/`KEPT_SOURCE`/`PASSTHROUGH`/`UNDECODABLE`) that the per-file line's vocabulary and this
summary both key off. Whatever the cache reports back as a decision's `status` today is one of
those four — a cache hit for a previously-`OPTIMISED` image still carries `status = OPTIMISED`
unless a fifth value is added.

Three ways this could land, with the trade-off each carries:

- **Invisible** (cache hit reuses whatever `status` the cached decision recorded, e.g.
  `OPTIMISED`): the summary line's arithmetic (`len(image_statuses)` and the per-status counts)
  keeps meaning exactly what it means today, but an author staring at "412 optimised" after a
  cache-warm run has no way to tell the run took two seconds instead of two minutes — the number
  that used to correlate with "how much work did this run do" no longer does, silently.
- **A fifth `ImageEncodeStatus` member** (e.g. a cache-hit status): every consumer of the enum has
  to be re-examined — `_format_image_decision_line` (`content_save.py:613-647`) pattern-matches on
  `decision.status`, so a fifth arm's exact wording joins the "fixed, greppable vocabulary" the
  existing spec (`spec_dd/3. done/2026-09-03_12:41_optimise-content-images/1. spec.md:303`)
  calls it. `test_content_save_image_output.py`'s parametrised cases would need a matching case
  for whatever this line renders on a hit, and the existing four-way exhaustiveness the tests
  currently assert (one case per status, `:147-155`) would gain a fifth without being told to.
- **A separate counter reported alongside, not inside, `image_statuses`** (a plain int of files
  served from cache, printed as its own clause): keeps the existing four-status vocabulary and its
  tests completely untouched, and gives the author both numbers — how many images were decided
  this run's way vs. history's way, and how many needed no work at all. Costs one more piece of
  state threaded through `save_content_to_db`'s loop (`:756-764`) and one more clause in the
  summary echo (`:1015-1016`).

**Recommendation, with reason:** a separate counter, not a fifth status and not silence. A fifth
status conflates two orthogonal questions the enum's own name distinguishes today — *what the
encoder decided about this image's pixels* (optimise / keep / pass through / fail) vs. *whether the
encoder ran at all this time* — and forcing a "cache hit" value into that enum means every existing
consumer that pattern-matches its four members (the per-file line, the tests) has to grow a fifth
arm for a fact that has nothing to do with the image's pixels. Silence is worse: this feature exists
because the run is currently slow, so the number one thing the author needs the summary to answer
after adopting a cache is "did the cache actually work," and burying that inside an unchanged
`412 optimised` line answers a question nobody is asking while hiding the one they are.

## 4. Non-image files: the cache is image-only, by what the code supports

`get_file_type_from_extension` (`content_save.py:575-593`) classifies five buckets:
`IMAGE`/`DOCUMENT`/`VIDEO`/`AUDIO`/`OTHER`, by extension only, no content sniffing. In
`save_file_to_db` (`:660-665`), the *only* branch that calls `optimise_image` is
`if file_type == File.FileType.IMAGE`. Every other type — a PDF, an `.mp4`, an `.mp3`, or an
unrecognised extension — falls straight to the `else` branch (`:691-693`): `stored_name =
file_path.name`, `encoded = None`, and the file is written verbatim with
`open(file_path, "rb")` / `DjangoFile(f)` at `:717-719`. There is no encode step, expensive or
otherwise, for documents, video or audio anywhere in this command. **The cache is image-only
because there is nothing else in this code path that does per-file transformation work to cache —
the brief's framing (WebP re-encode, ~420ms/1MB JPEG) is the entire set of expensive per-file work
`content_save` currently performs.** A document/video/audio cache would have no encode result to
cache against; it would only be caching "the bytes are unchanged since last run," a different
feature (skipping unchanged files entirely) that the settled-decisions list and the prior spec's
"Out of scope" section (`optimise-content-images/1. spec.md:29-31`, "Skipping unchanged files
between runs") both already treat as a distinct, not-yet-built thing.

## 5. Existing tests the cache must not break

All in `freedom_ls/content_engine/tests/test_content_save_course.py`, all building a
`tempfile.TemporaryDirectory()` tree per test (none of the image tests run against
`demo_content/`):

- `test_jpeg_image_is_stored_as_optimised_webp` (`:447-466`) — asserts `mime_type`,
  storage-name suffix, `file_path`, `original_filename` after one run. Unaffected either way: a
  fresh tempdir has no pre-existing cache, so this is always a cache miss on first run.
- **`test_repeated_save_produces_identical_stored_bytes` (`:469-492`)** — the one most directly
  about the property a cache changes. Docstring: "Two runs over the same tree each re-encode from
  the pristine source, so the stored bytes match." Asserts `first_bytes == second_bytes` across two
  `save_content_to_db` calls over the same tempdir. **With a cache, the second run's stored bytes
  would come from the cache written by the first run, not from a fresh re-encode** — the test's
  literal premise ("each re-encode from the pristine source") stops being true, though its
  assertion (byte-for-byte equality) still passes as long as the cache stores/returns exactly what
  the first run's fresh encode produced. This test's docstring becomes descriptively wrong even
  though its assertion keeps passing — the kind of drift that makes a test misleading rather than
  broken. It also exercises exactly the scenario in §7: a tempdir has no committed cache, so the
  first run performs the cache *write*, and this is the one existing test that would incidentally
  cover "write cache, then hit it" if a cache lands with no code changes to the test itself.
- `test_upgrade_run_removes_the_superseded_jpg_object_from_storage` (`:495-526`) and
  `test_superseded_jpg_object_survives_a_run_that_never_commits` (`:528-563`) — both pre-create a
  `File` row pointing at a `.jpg` object in storage, run `save_content_to_db` once, and assert the
  old storage key is gone (committed) or still present (rolled back / never committed). Both are
  fresh-tempdir, single-run tests with no pre-existing cache, so a first-run cache write does not
  change what either observes: the object being asserted on is the `course_media` storage object,
  which nothing about caching changes (settled decision: "nothing about how files are uploaded to
  `course_media` storage changes"). These are the deferred-delete tests named in the task brief;
  they are about storage-key lifecycle, not about the encode, and are content-cache-agnostic.
- `test_corrupt_image_is_stored_unchanged_and_run_completes` (`:566-583`) and
  `test_svg_image_is_stored_byte_identical` (`:586-603`) — both single-run, fresh tempdir. A
  corrupt image reaches `UNDECODABLE` and an SVG reaches `PASSTHROUGH`; whether either of those
  non-`OPTIMISED` outcomes is itself worth caching (re-detecting "still corrupt"/"still SVG" is far
  cheaper than an encode, so there is much less to gain) is a design question the brief's
  settled-decisions section does not close, and this research does not resolve it — flagged only as
  a fact these two tests would surface if a future cache-miss/hit boundary treated those statuses
  differently from `OPTIMISED`.
- `test_content_save_image_output.py` (all of it) — constructs `ImageEncodeDecision` values by
  hand and asserts `_format_bytes`/`_format_image_decision_line` output. Entirely decoupled from
  `optimise_image` and from any cache: nothing here changes.

**Tests against `demo_content/` that would start finding `_optimised/`:** none of the tests grepped
for `demo_content` assert on `File` rows or image bytes at all —
`test_demo_content_application_form.py` (a `loaded_demo_content` fixture at `:26-28` calling
`save_content_to_db(settings.BASE_DIR / "demo_content", site.name)`, marked `fls_internal`) checks
`Course`/`Form`/`FormQuestion` rows; `test_demo_content_form_link.py` and
`test_demo_content_picture_titles.py` (the latter reads the markdown source file directly, no
`save_content_to_db` call at all) don't touch images either. **`loaded_demo_content` does run the
real scanner over the real, on-disk `demo_content/` tree**, though — so if `demo_content/` ever
carries a committed `_optimised/` directory, this fixture is the one place in the test suite that
would walk it on every test run using it, and per §1 it is already correctly skipped by
`get_all_files`, so today's behaviour (this fixture passes) is preserved rather than at risk.

**Coverage floor:** `pyproject.toml:80`, `--cov-fail-under=73`, branch coverage on
(`--cov-branch`), sourced from `freedom_ls` only with `*/tests/*`, `*/migrations/*`, `*/conftest.py`
and `*/qa_helpers/*` omitted (`pyproject.toml:88-104`). The prior optimise-content-images spec
explicitly flagged this same floor as a risk for "pass-through branches are easy to leave
uncovered" (`optimise-content-images/1. spec.md:394`) — the same caution applies to a cache's
hit/miss branches, digest computation, and manifest read/write paths.

## 6. `demo_content/`: what a cache would add, and whether it should have one

`demo_content/` currently ships seven images total (per the Glob of the tree): six `.svg` files
(`diagram.svg`, `portrait.svg`, `square.svg`, `landscape.svg`, and two `graph1.drawio.svg` copies
under `functionality_demo_end_with_quiz/images/` and `functionality_demo_end_with_topic/images/`)
and one raster, `functionality_demo_content_widgets/images/backyard-drone-flight.jpg`, added by the
prior optimise-content-images feature specifically to exercise the resize/EXIF/lossy path (its own
spec says "around 1-2 MB," `optimise-content-images/1. spec.md:339`; the task brief here states it
at 1 MB).

Per §1, all six SVGs hit the `PASSTHROUGH` branch in `optimise_image` by suffix alone
(`images.py:146-151`), before any Pillow decode — there is no encode to cache for them, so caching
would add nothing for six of the seven files regardless of any decision about caching SVGs.
Only the one JPEG has an actual encode worth avoiding.

**What committing a cache for it would add to *this* repo:** one `_optimised/` directory containing
one cached WebP (on the order of 80-150KB per the optimise-content-images spec's stated target
band, `:423`) plus a `manifest.yaml`, under
`demo_content/functionality_demo_content_widgets/images/_optimised/`. Negligible in absolute size
next to the repo, and it is committed once, not regenerated per clone.

**Whether it should carry a cache, or stay cold:** Arguments either way, given the run this repo's
own test suite performs:

- *For* caching it: `test_demo_content_application_form.py`'s `loaded_demo_content` fixture runs
  `save_content_to_db` over `demo_content/` on every test session that uses it, which means this
  repo's own CI re-encodes that one JPEG every test run today. A cache would make that fixture
  (and any local `manage.py content_save demo_content <site>` a developer runs) faster, which is
  exactly the class of repeated-run cost the whole feature exists to remove — and `demo_content/`
  is the one content repository this codebase actually re-runs `content_save` against repeatedly
  in its own test suite, so leaving it cold forgoes the benefit in the one place this repo can
  measure it.
- *For* leaving it cold: `demo_content/` exists to be a demonstrable, readable example of "what a
  content repository looks like" — its own `README.md` and the fact that every other file in it is
  hand-authored markdown/YAML support that framing. A `_optimised/` directory with a `manifest.yaml`
  and a binary blob sitting next to `backyard-drone-flight.jpg` is exactly the kind of ingest
  artefact an author copying `demo_content/` as a template would have to notice is not something
  they authored — the settled decision that the cache is committed to *content* repositories in
  general does not by itself settle whether the *demonstration* content repository shipped inside
  the FLS repo should carry one, since its purpose (showing authors what to write) is different
  from a real deployment's content repository (getting fast repeated loads). One 1MB JPEG is also
  far short of "hundreds of images" — the case the brief motivates the whole feature with — so
  demo_content is not where the ~420ms/image, hundreds-of-images cost this feature targets is felt.

This research does not recommend one over the other; it surfaces that the two considerations above
(this repo's own CI re-running `content_save` over `demo_content/` repeatedly vs. `demo_content/`'s
role as a clean authoring example) pull in opposite directions, and whichever way the spec decides,
it should say so explicitly rather than leave it implied by "the cache is committed to content
repositories."

## 7. Transaction and atomicity: what a mid-run filesystem write survives a rollback

`save_content_to_db` is `@transaction.atomic` end to end (`content_save.py:739`), and the one place
it defers a side effect specifically because of that is the superseded-storage-object delete
(`:695-713`): deleting a same-key object inline is safe (`file_obj.file.delete(save=False)`,
`:711`, because the very next line overwrites that key so there is nothing to strand), but deleting
a *different*-key object (an extension change, e.g. `.jpg` -> `.webp`) is deferred with
`transaction.on_commit(partial(storage.delete, superseded_name))` (`:713`) specifically because "a
later step rolled this atomic run back" must not leave a `File` row naming a storage object that no
longer exists — the two tests in §5 (`test_upgrade_run_removes_the_superseded_jpg_object...` /
`test_superseded_jpg_object_survives_a_run_that_never_commits`) exist to prove exactly this
asymmetry.

Notice, though, that the *write itself* — `file_obj.file.save(stored_name, encoded, save=True)`
(`:716`) — is **not** deferred; it happens inline, inside the atomic block, before the transaction
has committed. So `content_save` already has a class of filesystem side effect (the new storage
object existing) that a rolled-back transaction cannot undo: if a later file in the same run raises
(e.g. the "silently dropped child" `ValueError` at `:1004-1007`), every `File` row from the whole
run is rolled back, but every storage object any earlier `file_obj.file.save(...)` call in that same
run wrote is **not** — it is simply an orphaned object nothing points at, and `content_save` accepts
that today (no test asserts otherwise; the two deferred-delete tests are about the *old* key being
cleaned up on a successful commit, not about strays from a failed one).

Writing a cache file into the content repository's own working tree during the run is the same
shape of hazard, transplanted from `course_media` storage onto the author's git checkout, with one
difference that matters and one that doesn't:

- **What doesn't change:** like the storage write, a cache write is additive, not destructive — it
  creates or updates a `manifest.yaml` entry and a `.webp` blob under `_optimised/`. If the run then
  fails and the transaction rolls back, no `File` row exists naming that cache entry (there is no DB
  row for a cache entry at all — the cache is filesystem-only per the settled decisions), so there
  is nothing for the rollback to have stranded a *reference* to. The cache entry is either later
  picked up as a valid hit on retry (harmless), or — if the source image it was computed from is
  itself later removed by the author before a retry — cleaned up by the orphan sweep the settled
  decisions already commit to ("orphaned cache entries... are deleted during the run"). Either
  outcome is self-healing on the very next run, which the storage-object orphan case above is *not*
  (nothing in `content_save` today sweeps orphaned `course_media` objects).
- **What does change:** the storage write lands in `course_media` — infrastructure the author does
  not see and git does not track. A cache write lands in the author's own working tree — files that
  `git status` will show as modified/untracked the moment the run returns, whether or not the run
  ultimately succeeded. A run that fails partway through a large content repository (say, on file
  200 of 400) would leave the author looking at a `git status` with `_optimised/` changes for the
  first ~200 image directories and none for the rest — a partial, inconsistent-looking diff that
  has nothing wrong with it (each entry present is individually valid, computed from that file's own
  pristine source) but reads as suspicious to a human reviewing it, purely because it is incomplete
  rather than because anything in it is wrong. `update_file_with_uuid` (`content_save.py:101-146`)
  already writes into the author's working tree today (backfilling a generated `uuid:` into the
  source file) — this is not a new *category* of side effect content_save performs, but it is a
  large increase in *how many* files a single run can touch this way, since a `uuid:` backfill
  happens once per new content item, while a cache write potentially happens once per image, every
  run that changes any image in a directory.

**Whether cache writes should be inline or deferred to commit, reasoned through:** deferring the
superseded-*delete* to `transaction.on_commit` is specifically about a **destructive** operation
whose direction of harm is asymmetric — do it too early and a rollback strands a row pointing at
nothing; do it too late (or never, on rollback) and nothing is lost, the delete simply doesn't
happen and the old object is still there next run to be re-evaluated. A cache **write** has no such
asymmetric-harm direction: it never destroys the only copy of anything (the pristine source image
on disk is untouched, and the DB `File` row it might describe is a separate, independently
rolled-back concern). Given that, deferring it to `on_commit` would only add a reason to (namely:
matching Django's `on_commit` pattern for consistency) without removing a hazard `on_commit` is
designed to prevent — the git-working-tree partial-diff hazard described above exists identically
whether the write happens the instant `optimise_image` returns or the instant the transaction
commits, because `on_commit` callbacks still run inside the same process, before `content_save`
returns to its caller; deferring to commit only helps when the concern is *"this DB row might not
end up existing,"* and a cache entry's validity was never contingent on any DB row's existence in
the first place. So: inline is at least as safe as deferred here, and deferred buys nothing the
existing mechanism was built to buy. The residual working-tree-diff hazard (a failed run leaving a
partial, if individually-correct, set of cache changes) is orthogonal to inline-vs-deferred and is
not solved by either — it would need something outside `transaction.atomic` entirely (e.g. writing
into a scratch location and only relocating into `_optimised/` once the whole run has succeeded),
which is a design question for the spec, not a fact this research can settle.

## 8. Anything else surprised by new directories inside content directories

Grepped `rglob`/`iterdir`/`glob(`/`walk(` across the repo (19 files matched); of those, only three
are content-directory scanners: `freedom_ls/content_engine/validate.py`,
`freedom_ls/content_engine/management/commands/content_save.py`, and
`claude_plugins/fls-content/validate/validate.py` — all three already covered in §1. The rest
(`freedom_ls/mail/...`, `freedom_ls/icons/...`, `freedom_ls/base/theming.py`,
`freedom_ls/accounts/...`, `docs/build_product_docx.py`, `claude_plugins/fls-dev/scripts/
compress_screenshots.py`, `claude_plugins/django-stack/scripts/generate_app_map.py`, test files)
walk unrelated trees (mail templates, icon sets, theme assets, legal-docs manifests, this repo's
own Python source) and never touch a content repository's directory structure.

`freedom_ls/content_engine/management/commands/content_validate.py` is a thin wrapper calling
`validate(path)` directly (`:1-9`) — it inherits whatever `get_all_files` does, no independent skip
logic of its own to re-check.

`docs/product/content-editing-workflow.md` already documents the underscore/dot skip convention in
authoring terms ("Any file or directory whose name begins with `_` or `.` is skipped by the content
scanner and never loaded, at any nesting level — a whole `_drafts/` directory or a single
`_topic.md`," line 25) and separately documents today's re-encode-every-run behaviour ("Course
images are re-encoded to WebP at ingest," line 10, and the fuller "Image optimisation" section,
lines 140). Both would need updating once a cache exists: the first sentence is already accurate
for `_optimised/` (no wording change needed, since it already says "any nesting level"), but the
second currently states unconditional per-run re-encoding as fact, which a cache would make false.

`claude_plugins/fls-content/skills/conventions/SKILL.md`'s own "Scanner skip rules" section
(`:75-88`) is the author-facing restatement of §1's rule and is already generic enough ("Names
starting with `_`") to cover `_optimised/` with no wording change; it is also explicit that this
plugin skill is a *description* of `validate.py`'s behaviour, which is the copy in §1 that has to
actually agree.

`claude_plugins/fls-content/skills/content-types/resources/course-files.md` and
`claude_plugins/fls-dev/skills/file-storage/SKILL.md` were checked directly (grepped for
`_optimised`/`optimis`/`cache`) and contain nothing that would need to change or that assumes
anything about a content directory's file population beyond the `_`/`.` convention already covered.

No QA helper command (`freedom_ls/qa_helpers/management/commands/*`) walks a content repository
directory tree — the two that matched the broader grep (`qa_create_dashboard_paging_fixtures.py`,
`qa_create_admin_constraint_fixtures.py`) build fixtures directly against the ORM, not by scanning
files.

---
status: ok
