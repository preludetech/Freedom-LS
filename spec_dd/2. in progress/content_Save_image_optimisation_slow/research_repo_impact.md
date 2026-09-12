# Research: what committing the `_optimised/` cache does to a content repository

Scope: the consequences of the already-settled decision to cache optimised images in
`_optimised/` subdirectories, committed to git alongside the source content. This does not
re-open whether to commit the cache, gitignore it, or use git-lfs — that is decided. It works
out what the decision costs and what it demands of the manifest format and the command's
output.

Source read: `freedom_ls/content_engine/images.py`, the image-handling section of
`freedom_ls/content_engine/management/commands/content_save.py`,
`claude_plugins/fls-content/skills/conventions/SKILL.md`, and
`spec_dd/3. done/2026-09-03_12:41_optimise-content-images/1. spec.md` (the prior spec that
built `optimise_image`/`ImageEncodeDecision` — its 80–150 KB band, its determinism guarantee,
and its "libwebp is not stable across its own versions" note are load-bearing for §1 and §7
below).

## 1. Size arithmetic

Take the example in the brief: 200 images, averaging 2 MB of source each — 400 MB of source
already resident in the working tree and, since content images are basically never re-encoded
smaller after the fact, already resident in `.git` history too.

**Working tree.** The optimiser's own target band is 80–150 KB per output (`SECOND_ENCODE_BYTES`
and the lossy/lossless split in `images.py` are tuned around that band; the prior spec's success
criteria state it explicitly). At the midpoint, ~115 KB × 200 ≈ **23 MB** added to the working
tree; at the extremes, 16–30 MB. `manifest.yaml` entries are a few hundred bytes of plain YAML
each (filename, a content hash, output size, format flags) — at ~150 bytes × 200 entries that's
~30 KB across every `manifest.yaml` in the tree, noise next to the images themselves. So the
cache grows the working tree by roughly **4–7.5% on top of the 400 MB of sources already
there** — a real but not dramatic addition.

**`.git`.** This is the part worth being precise about, because "git compresses everything" is
not true here. Git packs blobs with zlib deflate, which is a general-purpose entropy coder.
WebP output is *already* entropy-coded — the encoder's own arithmetic/Huffman stage has already
squeezed out the redundancy zlib looks for. Deflating an already-maximally-compressed byte
stream typically recovers low single-digit percent, sometimes 0%, and can occasionally cost a
few bytes of framing overhead on data that is functionally incompressible. So `.git` grows by
essentially the **same ~16–30 MB** the working tree gained on first commit — not some fraction
of it. Do not budget on git "packing the cache tighter."

Git also deduplicates identical blob content by hash, but that buys nothing here either: 200
distinct source photos each produce a distinct WebP blob, so there is nothing to dedup on first
commit. The one place dedup *does* help is idempotent re-runs — see §2.

Net effect of the one-off decision, at this example's scale: on the order of **30–60 MB total**
added across working tree and history combined, against a repository whose source images alone
already account for hundreds of MB in both. A low single-digit percentage of the repository's
existing footprint. Not free, but not the dominant cost either — the multi-MB source images
authors already commit are.

## 2. History growth over time

The working tree holds exactly one cache entry per source image at any moment (the orphan-delete
rule guarantees that). History holds every version ever committed. Three concrete scenarios:

**An author replaces one image.** One new WebP blob, ~80–150 KB, added to history permanently.
This is smaller than the source-image commit that necessarily accompanies it (source averages 2
MB), so the cache roughly adds 5–10% on top of a cost the repository already pays for the source
replacement itself. Not a real problem — it rides along with something already happening.

**An author re-crops fifty images.** 50 × ~115 KB ≈ **5.6 MB** of new cache blobs in one commit.
The accompanying fifty re-cropped sources, at 2 MB average, add ~100 MB to that same commit. The
cache addition is again a minority fraction (roughly 5%) of what the source change already
costs. Note also that git's delta/pack heuristics get little purchase between the old and new
cache blob for the same image: a crop changes the pixel content substantially, and WebP's
compressed bitstream does not have stable byte regions that track pixel-level edits the way, say,
a text file's lines do, so old and new versions of one image's cache entry pack close to
additively rather than as a small delta. This is true of the source image too, so it is not a
new cost this feature introduces — it is the same property JPEG/PNG sources already have.

**A developer changes a tuning constant (e.g. `LOSSY_QUALITY`) and every cached entry
re-encodes.** This is the one that actually hurts. Every image in the repository changes in a
single commit — for the 200-image example, ~23 MB added in one shot, with zero corresponding
author content change. Unlike the two scenarios above, nothing here rides along with an
already-necessary source commit: it is pure cache churn, and it touches every `_optimised/`
directory in the tree simultaneously, producing a single commit whose diff is hundreds of opaque
binary files with no meaningful review surface (see §5 on why that diff is unreviewable).

**Verdict.** At FLS's scale — hundreds of images per course repository — per-author edits (the
first two scenarios) are not a real problem: the cache rides along at a small fraction of the
source-image cost the repository already accepts. The global re-encode scenario is real but
occasional and structural, not continuous: it happens only when someone deliberately changes a
module constant in `images.py`, or (see §7) when the encoder toolchain itself drifts under an
author's feet. It should be treated as a known, rare, bounded event — expect one when the
constants are retuned, not a background drip — rather than as a reason to reconsider committing
the cache at all.

## 3. Merge and rebase behaviour

Binary `.webp` files have, in git's own words, "no well-defined merge semantics": on an unset
`merge` attribute git takes the current branch's version as the tentative result and marks the
path conflicted, requiring a human to pick a side (`git-scm.com/docs/gitattributes`). `.webp`
gets this treatment by default already, because git's binary-content heuristic sniffs it; §4
below is about making that explicit rather than relying on the heuristic.

**Two authors, two branches, both add new images to the same `images/` directory.** The source
files themselves merge trivially — different filenames, no overlap. The interesting case is
`manifest.yaml`, which both branches also modify, by appending one new entry each. Whether this
auto-merges depends entirely on how the manifest is shaped (see below): if each entry is a
self-contained block and the file has no shared preamble state, git's line-based three-way merge
resolves two non-overlapping insertions cleanly, the same way it resolves two authors adding
unrelated functions to the same source file. The new `_optimised/*.webp` blobs themselves never
conflict — they are new paths, not shared ones.

**Two authors, two branches, both change the *same* image.** The `.webp` blob conflicts, exactly
as described above, and has to be resolved as a binary pick (`git checkout --ours`/`--theirs`
`_optimised/photo.webp`, or take one author's replacement image outright) — there is no
meaningful "merge" of two different photographs. `manifest.yaml`'s entry for that one image also
conflicts, correctly: both sides touched the same block. This is not extra pain worth mitigating
— it is the merge tool correctly reporting that the two branches disagree about what this image
is, which is true. In practice the resolution is: resolve the binary conflict by picking a
source image, delete the disputed cache entry, and let `content_save` regenerate it — the
manifest conflict does not need hand-editing.

**What makes `manifest.yaml` merge cleanly vs. conflict constantly.** The distinguishing
property is whether the file's structure gives git's line-based algorithm independent,
non-overlapping hunks to work with:

- **Key ordering.** Entries must be written out in a stable, deterministic order (e.g.
  alphabetical by source filename) on every run. If the writer reorders entries that did not
  change — say, because a dict iterates in insertion order and insertion order shifted — every
  line in the file moves, and two branches that each touched one real entry will conflict on
  everything, because git sees the whole file as different. This is what breaks lockfile-style
  merging; it is the single most important property.
- **One entry per block.** Each image's data (source path, a content hash, output filename,
  output size, encode flags) needs to live together and be separated from its neighbours (a
  blank line or equivalent), so a diff hunk for one entry never overlaps the diff context of the
  entry next to it. This is what lets two unrelated additions land in different, non-adjacent
  parts of the file.
- **No shared counters or totals.** A `total_images: 200` or `count_optimised: 187` field at the
  top of the file is touched by *every* run regardless of which entries actually changed, so two
  branches that each add one unrelated image will still conflict on that one shared line, every
  time, even though their real work does not overlap.
- **No timestamps.** A `generated_at:` or per-entry `last_run:` field is, by definition, never
  the same between two runs, and carries no information a reader needs — it exists only to
  guarantee a conflict. Any such field turns "did the content change" into "did anyone run the
  command since," which is a different, uninteresting question that manufactures conflicts for
  free.
- **No run-level summary fields.** Anything that aggregates across entries (a per-status count,
  an "encoder version used this run" field recorded once at the top rather than per-entry) has
  the same shape as the counter problem: it changes whenever *anything* in the run changed, not
  when the specific entry a reviewer cares about changed.

The shape to aim for is a lockfile's shape: each entry is a self-contained fact about one source
image, sorted deterministically, with nothing in the file that summarises or counts across
entries. That is what package-manager lockfiles get right and is exactly why they are the
well-accepted case for committed generated files (§6).

## 4. `.gitattributes`

Per `git-scm.com/docs/gitattributes`:

- The `diff` attribute, when unset, makes git print `Binary files ... differ` instead of
  attempting a textual diff.
- The `merge` attribute, when unset, makes git "take the version from the current branch as the
  tentative merge result, and declare that the merge has conflicts" — exactly the binary-pick
  behaviour described in §3, and the documentation names this as "suitable for binary files that
  do not have a well-defined merge semantics."
- The built-in `binary` macro is literally `-diff -merge -text` — it is a convenience alias for
  setting all three at once, and the documentation's own example is `*.jpg binary`.

**Recommendation: `_optimised/**/*.webp binary`** (equivalently `-text -diff -merge`). This is
right for the same reason the documentation's own image example is right: there is no useful
textual diff of a WebP bitstream, no useful three-way merge of two different photographs, and no
line-ending normalisation that should ever touch compressed binary bytes. Git's own binary-sniff
heuristic would probably get all three right automatically, but declaring it explicitly in
`.gitattributes` removes any dependence on that heuristic (which works by sampling the first
several KB of a blob for a NUL byte, and is a heuristic, not a guarantee) and documents the
intent for anyone reading the repository's config.

**`manifest.yaml`: leave it as ordinary text, do not set `merge=union`.** `merge=union` runs a
line-based three-way merge but, on any line both sides touched, takes *both* versions instead of
conflicting — the documentation is explicit that "this tends to leave the added lines in the
resulting file in random order and the user should verify the result." Two traps specific to
this repository's workflow:

1. It is a **local-only** setting. GitHub, GitLab and Bitbucket's own web merge UIs do not honour
   a repository's `.gitattributes` merge drivers — only a local `git merge` does. Authors who
   resolve conflicts through a PR web UI (which FLS's workflow, hosted on git, likely includes)
   would get ordinary conflict markers there regardless of what `.gitattributes` says, while a
   teammate merging locally would get silent union merging — two different outcomes for the same
   conflict depending on which tool resolves it.
2. Union merging is blind to YAML structure. If both branches touched the *same* entry (§3's
   second scenario — two authors changing the same image), a union merge does not know that; it
   would happily interleave both versions' lines for that one entry, which — depending on exact
   line positions — can produce a YAML document with a duplicated key or a malformed block. A
   duplicate key in the merged manifest is a much worse failure than a conflict marker, because
   it can parse successfully and pick whichever duplicate PyYAML resolves last, silently.

The manifest's job is to merge cleanly *in the ordinary case* through the per-entry, sorted,
no-shared-state shape described in §3, and to conflict correctly and visibly in the genuine
conflict case. `merge=union` trades a visible, correct conflict for an invisible, possibly wrong
"success," which is the wrong trade for a file that both feeds `content_save`'s cache-validity
check and is read by humans reviewing a diff.

## 5. Author experience

`content_save` already mutates the working tree today — it writes a generated `uuid:` back into
a `.md`/`.yaml` file the first time it is saved (`update_file_with_uuid` in `content_save.py`).
So "this command edits my files" is not a brand-new idea to an author. What changes with the
cache is the *scale and kind* of mutation: instead of one text line in a file the author already
has open, a run can touch dozens of new binary files scattered across every `images/` directory
in the tree, none of which the author was looking at.

Concretely, walking through a session:

- **A dirty tree after what felt like a read command.** An author runs `content_save` to preview
  a wording change in one topic. `git status` afterwards shows that one intended file, plus new
  or modified files under every `_optimised/` directory the run touched — potentially unrelated
  to the edit they made, if this is the first run since the images were last cached, or if a
  dependency upgrade changed encoder output (§7). The signal-to-noise in `git status` drops
  sharply.
- **Staging is painful.** `git diff` on a `.webp` shows `Binary files a/... and b/... differ` —
  no content to review. `git add -p` cannot offer a hunk-by-hunk choice on a binary file; it is
  an all-or-nothing accept. An author who wants to stage only their real content edit and leave
  the cache alone for now has to `git add` specific paths by name rather than `git add -A` or
  `git commit -a`, which is a workflow discipline the tool does nothing to enforce.
  `_optimised/*.webp binary` (§4) at least stops git from trying to line-diff the blob, but it
  does not give the author anything to review.
- **Mixed commits.** Without that discipline, an unrelated typo fix and a pile of regenerated
  cache files land in the same commit, and a reviewer's PR diff is buried under binary file
  entries that carry no reviewable content — this is exactly the complaint the Hugo
  `resources/_gen` issue records (§6): "merging changes made simultaneously ... always requires
  manual arbitration," and reviewers cannot tell what changed from the diff.
- **Branch switching mid-run.** If an author runs `content_save` on branch A and then tries
  `git checkout branch-B` without committing, git refuses the checkout whenever the uncommitted
  cache changes would be overwritten by branch B's version of the same paths — an interruption
  that has nothing to do with why the author wanted to switch branches, forcing a stash, discard,
  or unplanned commit first. This is the same complaint the Hugo community documents needing
  `git checkout HEAD -- resources/_gen` to clear before some git operations will proceed.
- **Never committing the cache.** If an author leaves the regenerated `_optimised/` files
  uncommitted, every other clone (a teammate, CI, production) still has the old or absent cache
  and pays the full re-encode cost on its own next run — silently defeating the entire point of
  caching. Worse, an uncommitted cache sitting in the tree is easy to sweep into an unrelated
  later commit via `git add -A`, potentially one written by a different, drifted toolchain (§7),
  with nobody having reviewed it as a deliberate change.

**One mitigating property worth stating plainly, because it tempers all of the above.** The
prior spec's determinism guarantee — two consecutive `content_save` runs over an unchanged tree
produce byte-identical stored output — means the dirty-tree problem is triggered by genuine image
changes, not by merely running the command again. An author previewing content repeatedly during
a session does not accumulate spurious cache diffs on every run; only the first run after an
image actually changes (or after the toolchain drifts, §7) produces new bytes. The noise is real
but it is proportional to actual change, not to command invocations.

**What the command's output should tell authors, so none of this is a surprise.** The run
summary `content_save` already prints (`§4` of the prior spec — the per-file lines plus the
closing status counts) should say, explicitly, that files were written under `_optimised/` and
that they need to be committed alongside the content change — not left to the author to infer
from `git status`. The author-facing documentation this feature already owes
(`docs/product/content-editing-workflow.md`, per the prior spec's Documentation section) should
set the expectation before the author's first run, not after their first confused `git status`.

## 6. Prior art: committed build output

**Hugo's `resources/_gen`** is the closest analogue: a tool that writes derived, regenerable
assets into the working tree next to authored sources, offering a real speed benefit when the
cache persists. The community's settled position is to **gitignore it in the general case** —
the official community `.gitignore` template for Hugo lists `/resources/_gen/`
([github/gitignore](https://github.com/github/gitignore/blob/main/community/Golang/Hugo.gitignore)) —
with an explicit carve-out for ephemeral CI that has no other cache: "If you do a lot of asset
processing (especially images), builds can take minutes! If you discard the build cache each
time, you lose one of Hugo's key strengths"
([discourse.gohugo.io](https://discourse.gohugo.io/t/ignore-or-commit-resources-folder/23812)).
Hugo's own documentation-site repository commits the folder for exactly that reason. A separate
issue against a Hugo starter kit that *did* commit it records the two complaints this research
predicted independently: merge conflicts ("merging changes made simultaneously ... always
require manual arbitration to pick one of the two versions") and a permanently dirty tree
requiring `git checkout HEAD -- resources/_gen/assets` before some git operations will proceed
([okkur/syna-start#35](https://github.com/okkur/syna-start/issues/35)). This is essentially a
field report of §5's predictions from an unrelated project.

**Go's vendored dependencies** are a case *for* committing, but not directly comparable: the
recommendation is "almost always" commit `vendor/`, for reproducible builds, offline builds, and
protection against upstream disappearing
([blog.boot.dev](https://blog.boot.dev/golang/should-you-commit-the-vendor-folder-in-go/)).
Crucially, vendored Go source is **text** — it diffs and reviews like any other code change, so
committing it does not carry the binary-merge-conflict tax this feature's cache does. It is
evidence for "commit generated/fetched content when reproducibility matters," not evidence that
binary derived content merges painlessly.

**Bower's committed `dist/`** is the "we have no choice" case: Bower had no install-time build
hook, so a consumer's `bower install` could only get a working library if the built output was
committed to the package's own repository, not generated at install time
([knockout/knockout#1039](https://github.com/knockout/knockout/issues/1039)). This does not
apply to FLS: nobody consumes a course content repository without also having `content_save`
available to run against it — there is no "install-only consumer without the generator" the way
a Bower package's downstream user was. The ecosystem itself abandoned this pattern once npm's
lifecycle hooks made generating at install time possible.

**Committed lockfiles** are the well-accepted case, and the useful reference for *why* they work
where binary build caches don't: they are small, purely textual, line-oriented (so they diff and
mostly merge cleanly), and — most importantly — they capture a decision (which exact dependency
versions resolve) that cannot be perfectly and deterministically regenerated from the
project manifest alone across time, so committing them is the only way to pin what everyone
actually builds against.

**The general "generated files in git" debate** converges on the same litmus, argued explicitly
in Kent C. Dodds' widely cited post ([kentcdodds.com](https://kentcdodds.com/blog/why-i-dont-commit-generated-files-to-master))
and echoed in community threads
([graphql-code-generator#4253](https://github.com/dotansimha/graphql-code-generator/discussions/4253),
[a-h/templ#419](https://github.com/a-h/templ/discussions/419)): committing generated output is
right when either (a) a consumer needs the artefact and cannot or will not run the generator
themselves, or (b) regeneration is so expensive that everyone who needs the artefact benefits
from not paying that cost again, and there is no other shared cache. It is wrong when the
artefact is purely an internal build byproduct that every consumer's own tooling regenerates
cheaply on demand — the objections raised against that case are repo bloat, diffs that "make it
hard to identify when changes entered the codebase," merge conflicts, and contributors
accidentally editing the generated file instead of the source.

**Does FLS's case meet the bar?** It meets criterion (b), squarely: this whole feature exists
because `content_save`'s image re-encode is slow, every machine that runs it (author laptop, CI,
production deploy) pays that cost independently, and the settled design has no other shared
cache. It does **not** meet criterion (a) in the lockfile/vendor sense — there is no downstream
consumer of a content repository who lacks `content_save` and needs a pre-built artefact handed
to them; every party who touches the repository has the same tool. That places this closer to
Hugo's `resources/_gen` than to a lockfile or vendored dependencies: a pure build-speed cache,
committed because there is no other place to cache it, which is exactly why it inherits Hugo's
downsides (§5's dirty-tree and binary-conflict complaints) rather than a lockfile's comparatively
painless profile — a lockfile's ease comes from being small, textual and deterministic, and this
cache is binary and, at hundreds of images, not small (§1).

## 7. Fresh clone and CI

A machine that clones the repository gets both the source images and whatever `_optimised/*.webp`
+ `manifest.yaml` entries were last committed. What a subsequent `content_save` run does with
that depends on whatever mechanism validates a cache entry against its source (that mechanism is
out of this document's scope — it belongs to the caching design itself), but the risk worth
flagging here is specific to *what* that validation keys on.

**Decoding a cache hit written by a different Pillow/libwebp is safe.** WebP is a mature,
backward-compatible format: any conforming decoder — regardless of which encoder version
produced the bitstream — decodes it correctly. There is no correctness risk in serving, or
trusting as "already optimised," a `.webp` blob that was encoded on a machine with a different
Pillow build. The image a learner sees is unaffected by which machine wrote the cache entry.

**Reproducing a cache hit is a different question, and the answer is no.** The prior spec is
explicit that "libwebp's output is not promised stable across its own versions" and that Pillow
"re-cuts wheels with new bundled libwebp versions independently of this repo" — which is exactly
why that spec's own determinism test asserts run-to-run stability rather than a fixed golden
hash. The same fact matters here: if a machine with a different Pillow/libwebp were asked "does
this cached entry match what I would produce right now," the honest answer is "no, not
byte-for-byte," even though the source image has not changed and the cached bytes are perfectly
valid to keep using.

This has one concrete implication for whatever the cache-validity key turns out to be: it must
be keyed on the **source image's content**, not on anything derived from the encoder or library
version that produced the cached output. If validity ever depends on the output matching what
the current machine's encoder would produce today, then a routine dependency bump — `uv add`
or `uv lock --upgrade-package pillow` moving Pillow to a build with a newer bundled libwebp —
would invalidate every cache entry in the repository simultaneously, landing directly in §2's
"developer changes a tuning constant" scenario, except triggered by an unrelated dependency
update rather than a deliberate choice, and far more likely to happen without anyone realising
it would touch the image cache at all.

**CI.** A CI job that clones the repository, finds the committed cache, and validates entries
against source content only gets the full benefit: no re-encoding, no risk, because CI never
needs to judge whether the cached bytes are "the best possible encode," only whether they are a
valid, current one. The place version drift actually bites is the authoring workflow described
above — a developer whose local environment differs from whatever wrote the committed cache,
silently re-encoding and re-committing images nobody meant to touch.

---

status: ok
reason: researched size/history/merge/gitattributes/author-UX/prior-art/fresh-clone consequences of committing the _optimised/ cache; all findings sourced from the codebase (images.py, content_save.py, prior optimise-content-images spec) and cited web sources for prior art and git documentation
