# Cache optimised images in the content repository

`content_save` re-encodes every content image to WebP on every run, and throws the result away when
the run ends. The encode is the expensive part. A 1 MB JPEG in `demo_content/` costs about 420 ms, and
a PNG takes the lossless path at `ENCODE_METHOD` 6 and, above the size floor, a second lossy encode for
comparison. A course content repository holds hundreds of images, so an author who changed one sentence
in one topic waits minutes to see it, then pays again on the next run.

Nothing about that encode depends on anything that changed. `optimise_image` is a pure function of the
source bytes and a handful of module constants, and both already sit in the content repository. So keep
its output there too, committed alongside the source images, and re-encode only what actually changed.

## Where the cache lives

Beside the images it caches. A directory of images gets an `_optimised/` subdirectory holding the
optimised WebP files and one `manifest.yaml` describing them.

```
functionality_demo_content_widgets/images/
    backyard-drone-flight.jpg
    diagram.svg
    _optimised/
        manifest.yaml
        backyard-drone-flight.webp
```

The leading underscore is doing real work. All three copies of the content-scanner skip rule, in
`validate.py`, in `content_save.py`'s child discovery, and in the `fls-content` plugin's bundled
validator, already skip any path component starting with `_` or `.` at any depth. `_optimised/` is
invisible to every one of them the day it appears, with no new exclusion to write and no fourth place
to keep in sync. Note that `manifest` is also the word the `accounts` app uses for its legal-docs build
artefact. Different app, different format, no shared code.

## What makes a cache entry valid

An entry is keyed by the source filename as the author wrote it. It carries a SHA-256 digest of the
source bytes, the values of the `images.py` constants that shaped the encode, and everything
`content_save` prints about the image, so a hit produces the same author-facing lines as a fresh encode
without opening the image.

Keying on the source name, rather than on the digest or on the WebP's name, is what makes an orphan
obvious. An entry whose key is not a file in the directory has lost its source, and the run deletes it.
It also keeps a diff readable, showing `diagram.png`'s entry changing rather than one hash disappearing
and an unrelated one arriving.

**Digest, never mtime.** Every `git clone`, checkout and branch switch rewrites mtimes without touching
a byte. An mtime-keyed cache would miss on every entry in CI and on every fresh clone, the two cases
with the most to gain.

**Constants are compared by value.** If `LOSSY_QUALITY` moves from 80 to 75, the recorded 80 no longer
matches and the entry is a miss. Nobody has to remember anything for that to work.

**A hand-bumped version number covers what a constant cannot.** Changes to the decision logic itself,
like which formats get a second encode, how the never-grow guardrail compares, or where the camera EXIF
gate sits. Hashing the function's own source would catch those automatically, and would also invalidate
every image in every content repository over a renamed local variable. A deliberate integer is the
right granularity for a cache that lives in git.

**A Pillow or libwebp upgrade does not invalidate anything.** `pillow>=11.0` is a floor, so a routine
`uv lock --upgrade-package pillow` can change the bundled encoder with nothing in the diff to say so.
libwebp's output is not stable across its own versions, which is why the previous spec refused to assert
a golden hash in tests. Version-keyed invalidation would turn that upgrade into a silent rewrite of
every binary file in every content repository, tens of megabytes of permanent git history for a change
no learner can see. A stale WebP is still a correct WebP. Re-encoding after an encoder upgrade is a
decision someone makes once, deliberately, by bumping the version number.

## Which decisions get cached

`KEPT_SOURCE` above all. It is the most expensive outcome, not the cheapest. A full decode, a resize,
one or two encodes, and then the bytes are discarded because they came out no smaller. Caching only
`OPTIMISED` would leave the worst case being repeated every run.

`UNDECODABLE` is cached too. A corrupt file is a durable fact, and its error text cannot be
reconstructed without re-running the failure. `PASSTHROUGH` for animated GIF and for an already-small
WebP is cached for uniformity, so every image that reaches a decode has exactly one entry and orphan
detection stays a single rule.

SVG is the exception, and not for cost reasons. It returns on the suffix before Pillow is ever called,
so there is no decode to skip and nothing to record.

## When the cache is wrong

The cache is a speed optimisation over behaviour that is already correct without it, so almost
everything that can go wrong resolves the same way. Treat the entry, or the whole manifest, as cold,
re-encode from the pristine source, and overwrite. A manifest that fails to parse, whether half-merged
with conflict markers, truncated, or hand-edited into nonsense, cold-caches that one directory. An entry
whose WebP is missing or truncated is a miss. A `content_save` that a typo in a cache file can wedge
would be a worse failure than the slowness it was built to fix.

Recovered does not mean unmentioned. The run names a manifest that failed to parse, with its error, the
way `validate.py` already surfaces a YAML error. An author who committed a bad merge hears about it on
the next run instead of wondering why things got slow again.

One case is not self-healing. Two source images in one directory that differ only by extension both
target the same WebP name, and quietly picking a winner would serve one image's bytes against the
other's content on every run afterwards. That fails the run, which is how `content_save` already treats
a collection child it cannot resolve.

## What this costs the repository

For 200 images averaging 2 MB of source, the cache adds roughly 23 MB to the working tree and about the
same to `.git`. WebP is already entropy-coded, so zlib recovers almost nothing and nobody should budget
for git packing it tighter. Identical-blob dedup buys nothing either, since 200 distinct photos give 200
distinct blobs. Against the 400 MB of source images the repository already carries in both places, that
is a few percent.

Ordinary authoring rides along cheaply. A replaced image adds a cache blob of roughly 115 KB next to the
2 MB source commit that necessarily accompanies it. The one expensive event is a deliberate version bump,
which rewrites every entry in one commit with no author content change behind it. That is rare, bounded,
and exactly what the version number exists to make deliberate.

`research_repo_impact.md` has the full arithmetic, the merge and `.gitattributes` behaviour, and the field
reports from Hugo's `resources/_gen`, the closest analogue, which hit the same problems.

## What authors will notice

`content_save` already writes into the working tree, backfilling generated `uuid:` values into source
files. The cache is the same category of side effect at much larger scale. A run can touch binary files
across every images directory in the tree, none of which the author was looking at.

They get a dirty tree after a command that felt like a preview, a `git status` where their one real edit
is buried, and `Binary files differ` instead of a reviewable diff. Branch switching with uncommitted
cache changes gets refused. A cache left uncommitted defeats the whole point, because every other clone
still pays full price.

Two things make it liveable. The encode is deterministic, so re-running over an unchanged tree produces
no new bytes, which means the noise is proportional to real image changes rather than to how often the
command is run. And the run says so. Its output states that files were written under `_optimised/` and
need committing alongside the content change, rather than leaving the author to discover that in
`git status`.

Marking `_optimised/**/*.webp` as `binary` in `.gitattributes` stops git attempting a textual diff or a
three-way merge on a bitstream that has no meaningful version of either. `merge=union` on the manifest is
a trap and is not used. Only local merges honour it, no host's web UI does, and it resolves a genuine
two-author conflict by interleaving lines into a document that can parse with a duplicate key.

The manifest earns clean merges structurally instead. Entries sorted deterministically, one
self-contained block each, and no run-level field of any kind. No counts, no totals, no timestamp, no
encoder version hoisted to a header. Anything aggregate is a line that two unrelated single-image edits
both touch, which manufactures a conflict every time. This is the property that separates the lockfiles
that merge from the ones that do not, and `research_manifest_format.md` works through which got it right
and what an entry has to carry.

## What does not change

The `File` model, the `course_media` uploads, and the storage-key bookkeeping are untouched. Every run
still writes every file to storage whether its bytes changed or not, because `File` carries no digest to
compare against. Once encoding is cached that becomes the remaining cost of a run, particularly against a
real bucket. It is worth its own idea, and is deliberately not folded into this one.

`optimise_image` stays a pure function that knows nothing about caching. The cache is the caller's
concern, which is what keeps the encoder testable on raw bytes with no filesystem.

Only images are cached, because the encode is the only per-file work `content_save` does. Documents,
video and audio are written through verbatim.

`demo_content/` stays cold. It is the worked example authors copy as a template, and an `_optimised/`
directory holding a binary blob and a manifest next to the source image is ingest machinery they did not
author and would have to learn to ignore. It carries one real image, so there is little to win.

## Supporting research

- `research_cache_invalidation.md` covers what belongs in the key, why a hand-bumped version beats
  hashing the function source, and which outcomes are worth recording.
- `research_manifest_format.md` covers the fields an entry needs to reproduce the author-facing output,
  the keying collisions, and what makes committed YAML merge.
- `research_repo_impact.md` covers size and history arithmetic, merge and `.gitattributes` behaviour,
  author experience, and prior art on committed build output.
- `research_content_save_integration.md` covers the three copies of the skip rule, what `save_file_to_db`
  needs from a hit, the existing tests a cache would make descriptively wrong, and why a cache write
  belongs inline rather than deferred to commit.
