# Research: cache keying and invalidation for the `_optimised/` encode cache

Scope: given the settled shape — one `_optimised/` subdirectory per image directory, one `manifest.yaml`
per `_optimised/` directory, committed to git, orphans deleted on each run — what has to go into a
manifest entry for a cache hit to be safe, and what should happen when it isn't.

Everything below reasons from `freedom_ls/content_engine/images.py` (the current `optimise_image`,
its constants, `ImageEncodeDecision`/`ImageEncodeStatus`) and `freedom_ls/content_engine/management/
commands/content_save.py` (`save_file_to_db`, `_format_image_decision_line`, `is_skipped_path`,
`content_key`) as they stand today, plus the prior spec at
`spec_dd/3. done/2026-09-03_12:41_optimise-content-images/` and its research files.

## 1. What belongs in the cache key / validity check

**The source digest: SHA-256 of the raw source bytes, hex-encoded.** This repo already has a house
convention for exactly this — `freedom_ls/referral_tracking/counters.py:19-20`
(`hashlib.sha256(...).hexdigest()`) and `freedom_ls/webhooks/signing.py` both reach for SHA-256 rather
than anything faster or anything cryptographically stronger. Two reasons that convention transfers
here rather than being merely "consistent for its own sake":

- **Speed is not the constraint.** `hashlib.sha256` on OpenSSL's backend processes multi-MB buffers in
  low single-digit milliseconds; the encode this cache exists to skip costs ~420 ms for a 1 MB JPEG
  per the measurement in this problem statement. The digest is 1-2 orders of magnitude cheaper than the
  work it gates, so trading SHA-256 for MD5 or a non-cryptographic hash (xxhash, CRC32) would not move
  the run time and is not worth introducing a second hashing convention into the codebase for.
- **Collision resistance is not the reason to want it, but it's free.** This is a non-adversarial,
  locally-generated cache — nobody is trying to forge a source image that collides with another's
  digest — so a weaker hash would be *safe*, but SHA-256 costs nothing extra to get and matches what
  the rest of the codebase already reaches for, so there is no reason to pick anything else.

**Do not use file size, mtime, or path as a substitute or supplement for the digest as the "did the
source change" signal.** `git clone`/`checkout`/branch-switch rewrites every working-tree file's mtime
without touching a single byte, so an mtime-keyed cache would show a 100% miss rate on every fresh
checkout — the single most common way this cache would be exercised in CI or by a new contributor.
Content digest sidesteps this entirely by construction (see §5).

**Everything else that can change `optimise_image`'s output, enumerated:**

| Input | Changes output? | Should it invalidate the cache? |
| --- | --- | --- |
| `MAX_DIMENSION_PX`, `LOSSY_QUALITY`, `LOSSLESS_EFFORT`, `ENCODE_METHOD`, `SECOND_ENCODE_BYTES`, `LOSSY_WINS_DIVISOR` | Yes, directly — each is read inside the function on every call | Yes. Each is a plain value living in `images.py`; there is no reason not to record and compare it |
| `TRANSPOSED_ORIENTATIONS`, `SVG_SUFFIXES` | Yes, but only for inputs that hit that branch (EXIF orientation 5/6/7/8, `.svg`) | Yes, same reasoning — they are still plain constants |
| The decision logic itself (branch order, the `>=` in the never-grow guardrail, which formats get a second encode, etc.) | Yes — this is the thing the constants merely parameterise | Yes, but it cannot be *recorded as a value*; see §2 |
| Pillow's own version | Yes — Pillow's WebP plugin (`_encode`'s call into `Image.save(format="WEBP", ...)`), its JPEG `draft()` DCT-scaling behaviour, and `ImageOps.exif_transpose` are all Pillow code, not libwebp's | See §3 |
| The libwebp version Pillow's wheel bundles | Yes, for every `OPTIMISED` output — this is precisely the fact the prior spec's `1. spec.md` cites to justify *never* asserting a golden output hash in tests | See §3 |

Note that `pyproject.toml:37` pins `pillow>=11.0` — a floor, not an exact version — so a plain
`uv sync`/`uv lock --upgrade-package pillow` can silently change the installed Pillow *and* its bundled
libwebp with no corresponding line in `pyproject.toml` to diff against. Whatever records the library
identity has to read it at runtime (`PIL.__version__`, `PIL.features.version("webp")`), not infer it
from a lockfile diff.

## 2. Constants vs. a version number — recommend both, for different halves of the problem

**Record the constants literally, one field per tunable, compared against the module's current values
at read time.** This is mechanically derivable — a small mapping over the names already listed in
`images.py:56-87` — and it is correct by construction: if `LOSSY_QUALITY` moves from 80 to 75, the
recorded 80 no longer equals the live 75, the entry is a miss, and nothing about that step depends on a
human remembering anything. This closes off the entire class of "tuned a knob, forgot to signal it"
mistakes for every value that already has a name.

**But the decision logic is not a value**, and no set of recorded constants can catch a change to *how*
they are used — reordering the never-grow comparison, changing which source formats get a second
encode, changing the camera-EXIF gate. For that half, recommend a single hand-bumped `cache_version`
integer, incremented whenever a diff to `images.py` changes what bytes come out for some input, and
comment that requirement directly above the constant (not only in a spec document, where a future
diff's reviewer won't be looking).

**Rejected: hashing `optimise_image`'s own source as a stand-in for a hand-bumped version** —
`joblib.Memory`'s `func_key_mode="code"` is real prior art for exactly this idea (hash the function
body instead of trusting a human to bump a counter:
[joblib.Memory docs](https://joblib.readthedocs.io/en/latest/generated/joblib.Memory.html),
[PR #129](https://github.com/joblib/joblib/pull/129/files)). It removes the forgetting failure mode
entirely, which is attractive on paper. It is wrong for this specific cache because the artefact being
invalidated is not an ephemeral disk cache joblib owns privately — it is committed, versioned, binary
content in a content repository (§3 quantifies why that matters). A source hash invalidates on *any*
textual change to the function, including a renamed local variable or a reworded comment, and every
such incidental refactor would force a full re-encode of every image in every content repository built
against it — self-inflicted churn on ordinary code review, which is a worse failure mode than the one
being solved. A hand-bumped integer is invalidated only when a human deliberately says "this changes
output," which is exactly the granularity wanted.

**Honest cost of the hand-bumped half:** a developer can still change the logic and forget to bump
`cache_version`, and nothing will make that impossible. The mitigation is that this half of the key
covers a rare event (the decision logic in `images.py` changes far less often than the tunables do —
it hasn't moved since the prior spec landed it), it sits as one highly visible line in the same small
module as the constants it accompanies, and — per §3 — the same integer is also the one deliberate
lever for a library-driven re-encode, so it is a field a diff to this file's surrounding constants will
already draw a reviewer's eye to.

## 3. Library versions — do not invalidate automatically; fold "the encoder changed" into the same manual lever as logic changes

**Direction one: a stale cached WebP is not wrong.** It is a fully valid WebP file that decodes and
renders correctly in every browser this feature already commits to (`1. spec.md`'s WebP-not-AVIF
decision). The cost of *not* re-encoding it after a Pillow/libwebp bump is bounded: missing out on
whatever compression-ratio or encode-quality improvement the newer libwebp offers for that one file,
nothing more — there is no security or rendering-correctness defect analogous to, say, an unpatched
image-parsing CVE that would force the question.

**Direction two: not invalidating means the repository's stored bytes depend on history, not on the
source.** Two images with byte-identical source content, first ingested months apart across a Pillow
upgrade, would carry differently-encoded WebP forever, purely from *when* each was first optimised —
not from anything about the image itself or the current tunables. That is a real erosion of the
guarantee the prior spec cared about: its "Determinism" test asserts run-to-run stability precisely
*so that* the stored bytes are a pure function of the source and the current encoder, not of
incidental timing. A cache that never revisits library version turns "pure function of source + current
encoder" into "pure function of source + whichever encoder happened to be installed the first time,"
silently.

**The reconciling move: treat "the encoder changed" as the same category of event as "the decision
logic changed," gated by the one hand-bumped `cache_version` from §2, not by an automatic comparison
against the installed Pillow/libwebp version string on every run.** Concretely: do not record
`PIL.__version__`/`PIL.features.version("webp")` in the manifest and auto-invalidate whenever they
differ from the running interpreter's. Only invalidate on a library upgrade when a developer
deliberately bumps `cache_version` to say so. This lands in the same place as the prior spec's own
refusal to assert a golden hash in tests: that refusal was about not building *test* correctness on an
assumption libwebp doesn't keep. This cache doesn't build *cache* correctness on that assumption
either — nothing here claims cached bytes match what a fresh encode would produce right now; the
claim is only "these bytes are what the source, the recorded constants and the recorded
`cache_version` produced, and that triple hasn't changed." Whether to spend a deliberate re-encode pass
after a Pillow bump is a choice for whoever bumps Pillow to make consciously, once, in one reviewable
commit — not a side effect of routine dependency floor movement.

**Why automatic version-keyed invalidation would be the wrong default, quantified.** The cache lives
inside a git-committed content repository, and `pillow>=11.0` is a floor, so any `uv sync` or
`uv lock --upgrade-package pillow` anywhere downstream can bump the installed Pillow (and its bundled
libwebp) with zero corresponding diff to review. If that alone invalidated every `OPTIMISED` manifest
entry, then a routine, unrelated dependency bump would force a full re-encode of every raster image in
every content repository on its next `content_save` run — precisely the multi-minute cost this feature
exists to eliminate, recurring on a schedule nobody chose and nothing in the diff would explain. Worse,
because libwebp's own output is not promised byte-stable across its versions (the prior spec's own
citation for refusing a golden-hash test), every one of those re-encodes changes the actual stored
`.webp` bytes, not just re-derives the same bytes faster. Git has no useful delta compression between
two independently-recompressed WebP encodes of the same picture — unlike text, where a one-line change
produces a near-identical blob, two libwebp encodes of the same pixels at different library versions
can differ throughout the bitstream, so each is stored as a full new blob. For a course repository with
a few hundred images at 50-150 KB apiece, one silent Pillow bump would add tens of megabytes to git
history — permanently, since git history is append-only and nothing here proposes rewriting it — for a
change with no visible difference to any learner. That is the cost a hand-bumped, deliberate
`cache_version` is buying its way out of.

## 4. Caching the non-`OPTIMISED` outcomes

**`KEPT_SOURCE`: cache it, unambiguously.** It is named in the prompt as the single most expensive
outcome to reproduce — full decode, resize, one or two full encodes — and the only outcome where the
entire cost of a fresh run is paid for a result that is then thrown away (`decision.data is None`).
This is exactly the case this whole feature exists to stop paying for repeatedly. The manifest entry
needs `source_format` and `source_size` (both required by `_format_image_decision_line` at
`content_save.py:635-647` to print `"{format} {w}x{h}, re-encode not smaller, kept source."`) plus the
source digest and the constants/`cache_version` triple from §§1-3. No stored bytes and no `stored_size`
— the dataclass contract already sets both to `None` for this status, and the source file on disk *is*
what gets served, unchanged.

**`UNDECODABLE`: cache it.** A corrupt or malformed image is a durable fact about that file, not
something that changes run to run, so there is no reason to re-attempt a decode that is already known
to fail every time `content_save` runs, and no reason to recompute `decision.error`'s exact exception
text when it can be stored verbatim instead — it's the one field `_format_image_decision_line`'s
sibling `logger.warning` call needs and the one field that genuinely cannot be reconstructed without
redoing the failing operation. Cost of recording it is negligible: no bytes, just the digest,
`source_format`/`source_size` when Pillow got far enough to know them (both legitimately `None`
otherwise, per the dataclass contract), and the error string.

**`PASSTHROUGH` for animated GIF and for an already-small `WEBP`: cache them too, on the same low-cost
basis as `UNDECODABLE`, not because the per-run saving is large.** The GIF branch costs a frame-count
seek (`getattr(opened, "n_frames", 1)`, `content_save.py:167-176`) — cheap, but non-zero, and
proportional to how far into the file Pillow has to seek to find the end of the frame sequence for a
large or pathological GIF. The already-small-WebP branch costs only opening the file and reading
`.size`. Neither is expensive enough that skipping it is the point; recording them anyway is worth doing
because it keeps every image that reaches `Image.open` uniformly represented in the manifest — every
source file that was actually decoded gets exactly one entry, which is what makes the "no entry for
this source" signal in §5 unambiguous, and what makes orphan detection (already settled: entries with
no matching source are deleted) a single rule rather than one rule for "expensive" statuses and a
different one for "cheap" statuses.

**`PASSTHROUGH` for SVG: do not cache it at all — it is out of scope of the cache, not merely low
value.** The SVG branch (`images.py:146-151`) fires on the file's suffix alone, before `Image.open` is
ever called and before any bytes are decoded. There is no decode to skip, so a manifest entry for it
would not be caching anything — it would be bookkeeping for a decision that costs nothing to remake and
never touches `_optimised/` in either the cached or the uncached world.

## 5. Correctness guarantees

**What must be true for a hit to be indistinguishable from a fresh encode:** the recorded source digest
equals the current source file's digest; every recorded constant equals the module's current value;
the recorded `cache_version` equals the module's current value; and, for `OPTIMISED`, the `stored`
file the entry names actually exists and its bytes are what the entry claims (see below) — all four
have to hold, not just the source digest, or a hit is only "the source hasn't changed" rather than
"nothing that could change the output has changed."

For each way that can fail, in order of how defensible "recompute and overwrite" is over "raise":

- **A hand-edited `manifest.yaml`.** Treat the manifest as untrusted, disposable cache metadata, never
  as ground truth about the world — the same posture the run already takes toward its own re-derivable
  state elsewhere. Any field that fails to parse, or fails to match the current constants/`cache_version`/
  digest, is simply a miss: recompute from source and overwrite the entry. A human hand-editing a cache
  sidecar should cost at most one wasted re-encode, never an aborted run — a `content_save` that can be
  permanently wedged by a manifest typo is a strictly worse failure mode than one that quietly heals it.
- **A truncated `.webp` under `_optimised/`** (an interrupted checkout, a bad merge resolution, disk
  corruption). Verify before trusting a hit — at minimum, compare the stored file's actual size on disk
  against a recorded size, and prefer actually re-decoding it as WebP over trusting a size match alone,
  since a truncated file can coincidentally match a recorded length. On any mismatch: recompute from the
  pristine source and overwrite the stored file and its manifest entry. Never serve a truncated file to
  a learner because the manifest said it was fine.
- **A manifest entry whose `stored` file is missing** (deleted by hand, dropped in a merge). Identical
  treatment to "no entry at all": recompute and write both the file and the entry fresh. There is no
  information loss in treating "entry present, file absent" the same as "nothing recorded yet" — the
  entry alone was never sufficient to skip work.
- **A source file whose mtime changed but whose bytes did not** — the ordinary result of any
  `git clone`/`checkout`/CI pull. This is not a failure mode to handle defensively; it is a
  correctly-designed non-event, because mtime was never part of the key (§1). Worth stating explicitly
  so nobody "improves" this later by adding an mtime shortcut ahead of the digest check — that would
  reintroduce the exact bug a content-digest key was chosen to avoid.
- **Two entries claiming the same stored filename.** This is the one case where recompute-and-overwrite
  is *not* defensible, because overwriting means one source image's cached artefact silently replaces
  another's, and the run would then serve the wrong bytes against a different source file's row on
  every subsequent hit — a correctness break, not a wasted re-encode. This can arise today because
  `save_file_to_db` derives the stored name from `file_path.with_suffix(decision.suffix).name`
  (`content_save.py:689`), so two source images differing only in extension in the same directory (a
  stray `photo.jpg` beside `photo.png`) already target the same `.webp` name. The manifest entry's
  identity should be the *source* filename, not the *stored* filename, so a collision on the stored
  name surfaces as "two different entries agree on one stored file" and the run should raise rather
  than pick a winner silently — the same posture `save_content_to_db` already takes for an unlisted
  collection child (`content_save.py:1001-1007`: *"A silently dropped child is a course missing content
  nobody notices, so this fails the whole atomic load instead"*). An ambiguity that would otherwise
  serve the wrong image to a different piece of content and nobody would notice deserves the same
  treatment here.

## 6. Prior art

- **Hugo's `resources/_gen` — the closest built-time analogue, and it is *not* committed by Hugo's own
  default scaffold, but Hugo's community explicitly recommends committing it for exactly FLS's reason.**
  A fresh `hugo new site` does not ship a `.gitignore` that includes `resources/`; the community default
  is to gitignore it as a regenerable build artefact. But Hugo's own documentation and its maintainers'
  guidance in community discussion is that CI/deploy-triggered builds "can be significantly faster if
  you include this directory in source control"
  ([discourse.gohugo.io/t/what-do-i-commit-to-git/52247](https://discourse.gohugo.io/t/what-do-i-commit-to-git/52247)) —
  the same build-time-cost argument this feature is built on, not a difference in philosophy. Hugo keys
  a processed image on the source resource plus the processing operation applied to it (`.Resize`,
  `.Fit`, etc. — the operation string itself is part of the key), and the cached file's name embeds a
  hash derived from that pairing (e.g. `sunset_hu59e56ffff1bc1d8d122b1403d34e039f_90587_ed7740a9....jpg`)
  ([gohugo.io/content-management/image-processing](https://gohugo.io/content-management/image-processing/)).
  Translated to FLS: Hugo's "operation string" is FLS's "recorded constants + `cache_version`" — both
  are "what was asked for," not just "what the source was." Hugo's file cache config also documents a
  `maxAge: -1` default (`gohugo.io/configuration/caches`) meaning entries never expire on their own —
  the same posture recommended in §3, invalidation is deliberate, not automatic on the calendar.
- **Gatsby's `.cache` (`gatsby-plugin-sharp`)** keys on the source's `contentDigest` plus "the
  meaningful arguments, e.g. cropFocus, image format, grayscale, etc."
  ([github.com/gatsbyjs/gatsby/issues/6999](https://github.com/gatsbyjs/gatsby/issues/6999)), and
  separately invalidates its whole cache when `package.json`/`gatsby-config.js`/`gatsby-node.js` change
  ([gatsbyjs.com/docs/build-caching](https://www.gatsbyjs.com/docs/build-caching/)) — i.e. Gatsby's own
  answer to "did the pipeline itself change" is also a coarse, file-level signal, not a per-parameter
  diff, which is the same shape as this file's recommended `cache_version` rather than an automatic
  library-version comparison.
- **Next.js's on-request image optimiser** keys its cache on `(url, width, quality, format)`, with
  `quality`/`format` restricted to an explicit allowlist as of Next 16
  ([nextjs.org/docs/app/getting-started/images](https://nextjs.org/docs/app/getting-started/images)).
  Its per-call escape hatch is `unoptimized={true}`, and the documented gotcha is that a global
  "unoptimized" setting cannot be overridden back to "optimised" per image
  ([github.com/vercel/next.js/issues/85208](https://github.com/vercel/next.js/issues/85208)) — a
  one-way escape hatch. This translates as a caution for FLS's *manifest*, not its opt-out surface
  (already out of this topic's scope): whatever field says "this cache entry is stale," make sure it
  can be flipped both ways by construction rather than being a one-way ratchet, which the recompute-on-
  mismatch design in §5 already satisfies (a match always wins, regardless of history).
- **`imagemin`/`sharp`-based build pipelines** have no well-documented public cache-keying scheme of
  their own to translate from; `imagemin-sharp` is unmaintained and its caching (where plugins like
  `unplugin-imagemin` add one at all) is described only as "supports cache mode," with no published key
  shape. Not usable as prior art beyond confirming that most of this ecosystem treats caching as a
  wrapper concern bolted onto the encoder, not something the encoder itself is aware of — which matches
  keeping `optimise_image` a pure, cache-unaware function and putting all of this keying logic in the
  caller, as it already is (`images.py`'s own docstring: "Pure bytes in, bytes out ... testable on raw
  image bytes with no database").
- **Eleventy Image's `.cache`** writes transformed files to disk during build and skips the transform
  "if the output file for that source+params already exists"
  ([syntackle.com/blog/eleventy-image-html-transform-plugin-disk-cache](https://syntackle.com/blog/eleventy-image-html-transform-plugin-disk-cache/),
  [zachleat.com/web/faster-builds-with-eleventy-img](https://www.zachleat.com/web/faster-builds-with-eleventy-img/)).
  Its public documentation does not go into cache-key composition or dependency-version invalidation in
  enough detail to translate a concrete mechanism from, beyond confirming the same "source + params,
  presence-check before regenerating" shape as everything else here.
- **`diskcache`/`joblib.Memory`** are the Python-side precedent already cited in §2:
  `joblib.Memory`'s default key hashes the call's *arguments*, cryptographically
  ([joblib.readthedocs.io/en/latest/memory.html](https://joblib.readthedocs.io/en/latest/memory.html)),
  and its `func_key_mode="code"` option additionally hashes the function's own source so a logic change
  invalidates automatically
  ([PR #129](https://github.com/joblib/joblib/pull/129/files)). Translated for FLS: the "arguments"
  half is exactly this cache's source digest plus recorded constants (§1); the "hash the code" half is
  the mechanism explicitly rejected in §2 in favour of a hand-bumped `cache_version`, because unlike a
  private `joblib` cache directory that nobody reviews or commits, this cache's invalidations are
  binary-diff churn in a reviewed, git-committed content repository, where a spurious hash change from
  an incidental refactor is a cost joblib's use case never pays.

## Summary of recommendations

1. Key on a SHA-256 digest of the source bytes — the house convention, and fast enough relative to the
   encode that no faster hash is worth the inconsistency.
2. Record every named constant in `images.py` literally, compared value-for-value, plus one
   hand-bumped `cache_version` integer for everything a constant can't express: the decision logic's
   shape, and — deliberately, not automatically — a Pillow/libwebp upgrade a developer has decided is
   worth a full re-encode pass.
3. Never key automatically on the installed Pillow/libwebp version. A stale WebP is still correct; an
   automatic version-keyed cache would turn every routine dependency bump into an unreviewed,
   unexplained rewrite of every binary file in every content repository.
4. Cache `KEPT_SOURCE` and `UNDECODABLE` unconditionally, and `PASSTHROUGH` for GIF/over-cap-WebP for
   manifest uniformity; never cache SVG `PASSTHROUGH`, which never reaches a decode in the first place.
5. Treat the manifest as disposable and self-healing for every failure mode except a stored-filename
   collision between two different source images, which is a correctness break and should raise, not
   silently pick a winner — consistent with how this command already treats an unresolvable collection
   child.

status: ok
