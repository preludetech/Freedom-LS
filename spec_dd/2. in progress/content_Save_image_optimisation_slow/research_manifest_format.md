# Research: shape of the `_optimised/` cache manifest

Topic: given the settled decisions (cache lives in `_optimised/`, one manifest per
`_optimised/` directory, orphans deleted, only the encode is cached), work out what the
manifest file actually contains and how it is shaped — fields, keying, merge-friendliness,
robustness, format, and filename.

Source read: `freedom_ls/content_engine/images.py` (`ImageEncodeDecision`,
`ImageEncodeStatus`, `optimise_image`), `freedom_ls/content_engine/management/commands/content_save.py`
(`save_file_to_db`, `_format_image_decision_line`, `_format_bytes`, `PreservingDumper`/`represent_str`),
`freedom_ls/content_engine/validate.py` (`get_all_files`, `is_skipped_path`),
`claude_plugins/fls-content/skills/conventions/SKILL.md`, `.claude/skills/domain-glossary/SKILL.md`,
and `freedom_ls/accounts/management/commands/build_legal_docs_manifest.py` /
`freedom_ls/accounts/legal_docs.py` for the one other place FLS already uses the word "manifest".

---

## 1. Fields

Start from what a cache **hit** has to reproduce, byte-for-byte, in place of a fresh
`optimise_image()` call:

- The same `ImageEncodeDecision` the encoder would have returned (so `save_file_to_db` doesn't
  need a second code path for "decision came from cache" vs "decision came from encoding now").
- The same two author-facing lines: `_format_image_decision_line(decision)` and, when
  `decision.data is not None`, the `_format_bytes(before) -> _format_bytes(after) (pct%), status.`
  line in `save_file_to_db`.
- Enough to know, cheaply (i.e. without opening/decoding the source image), whether this cache
  entry still matches the current source file — that's `research_cache_invalidation.md`'s
  question of *which* validity fields, but the manifest format has to leave room for them.

Walking `ImageEncodeDecision`'s own fields against that requirement:

| `ImageEncodeDecision` field | Needed on a cache hit? | Reasoning |
|---|---|---|
| `status` | **Yes** | Every line in `_format_image_decision_line` branches on it first. |
| `source_format` | **Yes** | Printed in every branch except the one where it's `None` (decode failed before Pillow could name a format). Also distinguishes "JPEG re-encoded to WebP" from "already-WebP passthrough" for the author. |
| `source_size` | **Yes, when not `None`** | Printed as `{w}x{h}` in the OPTIMISED, KEPT_SOURCE and PASSTHROUGH-with-size branches. |
| `data` | **No — not stored in the manifest** | This is the cached *file*, not a manifest field: it already lives in `_optimised/<name>.webp` as its own bytes. Duplicating it into YAML (base64) would make the manifest itself large and defeat the point of caching (git would then store the bytes twice: once in the stored file's own blob, once inline in the manifest text). |
| `suffix` | **Derivable — drop it** | `".webp"` whenever `status == OPTIMISED`, and absent otherwise. It's implied by `status` plus the stored file's own extension (which the manifest's key/filename already carries — see §2). Not stored as a separate field. |
| `mime_type` | **Derivable — drop it** | `"image/webp"` is a constant of `status == OPTIMISED`; nothing else. |
| `lossless` | **Yes** | The one bit `_format_image_decision_line` can't re-derive: it decides the printed word `lossless`/`lossy`. Not recoverable from the stored WebP without decoding it, and decoding it is exactly the cost a hit exists to avoid. |
| `stored_size` | **Yes** | Printed as the target `{w}x{h}` in the OPTIMISED line. Could in principle be read from the stored WebP's own header (cheap, no full decode) — but the source dimensions require decoding the *source*, which is precisely the "hundreds of images, cache does this" problem the manifest solves, so storing both alongside each other keeps the hit path uniform (no partial re-open of anything) and keeps the manifest self-describing without depending on a second file read succeeding. |
| `error` | **Yes, only when `status == UNDECODABLE`** | Printed by neither `_format_image_decision_line` nor the byte line, but `save_file_to_db` logs it (`logger.warning(f"Could not decode {relative_path}: {decision.error}")`). A cache hit for an undecodable image still has to reproduce that log line without re-attempting the decode that produced it. |
| `source_size` for `PASSTHROUGH`/`KEPT_SOURCE`/`UNDECODABLE` | **Yes, when Pillow got that far** | Same reasoning as the OPTIMISED row — all read straight off `ImageEncodeDecision`. |

So an entry needs: `status`, `source_format` (nullable), `source_size` (nullable pair),
`lossless` (only meaningful when `status == optimised`), `stored_size` (only meaningful when
`status == optimised`), `error` (only meaningful when `status == could not decode`). That is
six author-facing fields, three of them conditionally absent depending on `status` — the same
shape `ImageEncodeDecision` itself already has (fields set together or not at all, per its own
docstring). A manifest entry should mirror that discipline: no field present that its `status`
doesn't call for, so a reader can't accidentally treat a stray `lossless: false` on a
`kept source` entry as meaningful.

Two more fields exist that aren't part of `ImageEncodeDecision` at all, because
`ImageEncodeDecision` is stateless per-call and a cache entry has to persist across runs:

- **A validity fingerprint** (source digest and/or encoder parameter version). This is the
  subject of `research_cache_invalidation.md` — this file only needs to say *that* the entry
  carries it, and *where*. It belongs alongside the other per-entry fields, at the top level of
  the entry (not nested under a `cache:` or `meta:` sub-key), because it is exactly as much a
  property of "is this entry still good" as `status` is of "what did the encode decide" — an
  entry is one indivisible fact about one stored file, not two facts glued together.
- **Nothing else.** No `stored_bytes`/file size as a separate field: it is recoverable by
  `stat()`-ing the stored file directly if ever needed for display, and `_format_bytes` already
  takes its *before* size from the live source read, not from the manifest — a manifest field
  for it would be one more thing that could drift from the file it describes.

### Concrete example (three entries, three statuses)

```yaml
logo.webp:
  status: optimised
  source_format: PNG
  source_size: [512, 512]
  lossless: true
  stored_size: [512, 512]
  digest: sha256:3b1c...e04a
diagram.svg:
  status: passthrough
  source_format: SVG
photo-01.webp:
  status: optimised
  source_format: JPEG
  source_size: [4032, 3024]
  lossless: false
  stored_size: [1600, 1200]
  digest: sha256:9af2...11c0
corrupt-scan.jpg:
  status: could not decode
  source_format: null
  error: "UnidentifiedImageError: cannot identify image file"
  digest: sha256:71e0...abcd
```

(`digest` here is a placeholder for whatever `research_cache_invalidation.md` settles on —
shown only to demonstrate where it sits: a sibling of `status`, not a nested object.)

Note `KEPT_SOURCE` isn't shown as a distinct example above only because its shape is identical
to `passthrough`'s (`source_format` + `source_size`, no `lossless`/`stored_size`/`error`) — the
`reason` word ("re-encode not smaller") that `_format_image_decision_line` prints for it is
derived from `status` alone at print time, not stored.

---

## 2. Keying

**Recommendation: key each entry by the *stored* filename** (the name the optimised output is
written under inside `_optimised/`, e.g. `logo.webp`), **not** by the source filename and not by
the digest.

Walk the collision cases in one directory:

- **Two sources, one stored name.** `logo.png` and `logo.jpg` sitting side by side both produce
  `logo.webp` under the current `file_path.with_suffix(".webp")` naming rule in `save_file_to_db`.
  If the manifest were keyed by *source* filename (`logo.png:` / `logo.jpg:` as two entries),
  both entries would legitimately claim to own the same stored file, and nothing in the manifest
  format would catch that they can't both be right — the second `content_save` run would
  silently overwrite the first's stored bytes while both manifest entries kept claiming a hit.
  Keying by *stored* filename makes this collision visible as what it structurally is: two
  YAML mapping keys trying to be `logo.webp:` twice, which a plain dict literally cannot express
  in the same document, so the ambiguity surfaces immediately rather than later, in storage.
  (Whether `content_save` should then refuse the run, or pick a resolution order — is a decision
  for the idea/spec itself, not this research file's job to make. But keying the manifest by
  stored name is what turns the collision into something the format itself exposes, rather than
  a corruption two runs later.)
- **A source with no encode (`PASSTHROUGH`/`KEPT_SOURCE`/`UNDECODABLE`).** Here the "stored"
  file is just the original, unrenamed — so its key is still its own filename, and there's no
  new collision to worry about beyond ordinary same-directory filename uniqueness, which the
  filesystem already guarantees.
- **Case sensitivity.** `Diagram.PNG` and `diagram.png` cannot coexist on a case-insensitive
  filesystem (macOS default, Windows) but can on Linux/ext4, which is what most CI and
  production hosts run. Two authors, one on each kind of machine, could each commit a file that
  the other's checkout would silently collide with — that's a source-tree hazard independent of
  the manifest, but the manifest inherits it: whatever the manifest keys on has to preserve case
  exactly as authored (`sort_keys`/comparison must be ordinary string ordering, not
  case-folded), so that a manifest generated on Linux is byte-identical to one that would be
  generated from the same tree on macOS. Keying by stored filename doesn't make this problem
  worse or better than keying by source filename would — it's a pre-existing property of
  authoring content on git — but it means the manifest format itself must not attempt any
  case-normalisation of keys, or it would introduce a *second* source of divergence on top of
  the filesystem's own.

Keying by **digest** was considered and rejected: it would make the manifest's on-disk key
change every time an author touches the source image (expected — a changed image should get a
new digest) but would also mean the diff shows an entry vanishing under one key and reappearing
under another, rather than the same author-facing filename's entry simply updating in place —
worse for review, since a reviewer reading the diff wants to see "`logo.png`'s encode changed,"
not "an entry with an unfamiliar hash was deleted and a different unfamiliar hash was added."
Keying by stored filename keeps the key stable across ordinary content edits (same picture,
recompressed) and lets the digest live as a plain field inside the entry, where a diff shows it
changing — which is exactly the fact a reviewer needs to see.

---

## 3. Diff and merge friendliness

What makes a committed YAML file merge cleanly, distilled from four real lockfiles' documented
merge behaviour:

- **Deterministic key ordering.** uv's `uv.lock` sorts entries by package name so "the same
  input always produce[s] the same output" — two authors who each add one image get diffs that
  land in different, predictable places rather than colliding on where the new block gets
  inserted ([Lockfile Format Design and Tradeoffs](https://nesbitt.io/2026/01/17/lockfile-format-design-and-tradeoffs.html)).
  For the manifest, that means dumping with `sort_keys=True` (alphabetical by stored filename) on
  every write, never in insertion or directory-scan order.
- **Block-per-entry, no nesting.** Cargo.lock's redesign explicitly optimised for this: entries
  became independent `[[package]]` blocks, and checksums moved from a shared `[metadata]` table
  onto each entry directly, specifically "to generate less git merge conflicts" ([rust-lang/cargo#7070](https://github.com/rust-lang/cargo/pull/7070)).
  The failure mode this avoids is package-lock.json's: a deeply nested tree where "one small
  package update" cascades into changes at every level of nesting above it, and edits from two
  branches land inside overlapping structural boundaries even when they touch unrelated
  packages, which is exactly why manual resolution of `package-lock.json` conflicts is not
  recommended and tooling (`npm-merge-driver`) exists purely to regenerate it instead of merging
  it ([resolving package-lock.json conflicts](https://gist.github.com/szemate/6fb69c8e3d8cce3efa9a6c922b337d98)).
  The manifest's flat `{stored_filename: {fields...}}` shape with no wrapping list, no shared
  index, and no cross-references between entries gets this for free — it's the same shape §1
  already arrived at for other reasons.
- **No run-level aggregates.** Poetry's `content-hash` is a single hash of the whole
  dependency‑constraint surface, stored once per file; touching *any* dependency changes that
  one shared field, so two branches that each add an unrelated dependency collide on the
  content-hash line even though their actual entries don't overlap — "concurrent changes to any
  part of the file will cause merge conflicts" in that field specifically
  ([How to resolve a git conflict in poetry.lock](https://www.peterbe.com/plog/how-to-resolve-a-git-conflict-in-poetry.lock),
  [poetry#496](https://github.com/python-poetry/poetry/issues/496)). Pipfile.lock has the
  same shape of problem in its `_meta.hash.sha256` field, though contained to that one field
  since the rest of Pipfile.lock is a flat, alphabetically-keyed dict. The manifest must carry
  **no directory-level or run-level field at all** — no entry count, no "last generated at"
  timestamp, no aggregate byte-total, no encoder-version-for-the-whole-file header. Anything
  aggregate is a field two unrelated single-image edits will both need to touch, guaranteeing a
  conflict on every concurrent edit regardless of which images changed. If a per-entry encoder
  version is needed for invalidation (`research_cache_invalidation.md`'s territory), it goes on
  the entry, never hoisted to a shared header.
- **Nothing changes when nothing changed.** A re-run over an unchanged source tree must produce
  byte-identical YAML to what's already committed — same key order, same quoting, same line
  endings — or every run poisons `git diff`/`git blame` with no-op churn regardless of whether
  any image actually changed. This is the sharpest version of the previous point: it's not just
  that aggregates must be absent, it's that the *serialisation itself* must be idempotent given
  identical input. `yaml.dump(..., sort_keys=True, default_flow_style=False)` with no
  timestamp/counter fields gets this; a hand-rolled writer that preserves insertion order or
  appends new entries at the end would not.
- **Gemfile.lock**, mentioned in the task background implicitly via the lockfile family, uses
  indentation-significant nesting to express the dependency tree and is called out in the same
  source as "structurally hostile to merging" for the same reason as package-lock.json — another
  data point against any nested-object manifest shape ([Lockfile Format Design and Tradeoffs](https://nesbitt.io/2026/01/17/lockfile-format-design-and-tradeoffs.html)).

**Is `PreservingDumper`/`represent_str` relevant here?** No. That machinery exists in
`content_save.py` to round-trip *author-authored* multi-line markdown-adjacent prose (topic
`content:`, question text) back into a YAML file without mangling it into an ugly quoted
one-liner — its whole purpose is preserving a human's literal-block formatting choice across a
read-modify-write cycle of a file a human primarily edits. A manifest entry has no multi-line
string fields at all (see §1's field list) and is not a file a human is expected to hand-craft
the prose of — it's closer in spirit to `uv.lock` than to a content topic. A manifest wants a
plain, boring, fully-deterministic `yaml.safe_dump`-style writer with `sort_keys=True`,
`default_flow_style=False`, no custom representers, and no literal-block styling, because literal
block style is exactly the kind of "preserve what a human typed" feature that's actively unhelpful
for a file with no prose fields and a hard idempotence requirement — using `PreservingDumper`
here would risk it treating a long `error` string specially (block style) versus a short one
(quoted), which is one more axis on which two semantically-identical runs could diverge in their
byte output.

---

## 4. Robustness

The manifest is a plain file sitting in an author's git working tree, so it will occasionally
be hand-edited, half-merged, truncated by a bad checkout, or missing the file it describes. Case
by case:

| Situation | What `content_save` should do |
|---|---|
| Manifest file is absent | Cold cache for that directory: every image in it is encoded fresh, and the manifest is (re)written from scratch at the end of the run. This is also day-one behaviour for a repo that predates the cache feature — no special-casing needed. |
| Manifest parses, but an entry's stored file is missing on disk | Treat that one entry as a miss (re-encode the source, rewrite the stored file and the entry), and treat every *other* entry in the same manifest as read normally. One dangling entry must not invalidate its siblings. |
| Manifest has conflict markers still in it (`<<<<<<<`, `=======`, `>>>>>>>`) | This is not valid YAML — `yaml.safe_load` raises `yaml.YAMLError` on it. Caught, logged/reported (see below), and the *whole directory's* manifest is treated as absent: cold-cache that directory, re-encode everything in it, and overwrite the file with a clean, correct manifest. There is no safe way to partially trust a document that failed to parse at all. |
| Manifest is truncated (valid YAML prefix, file cut off mid-write) | Same as the conflict-marker case if it fails to parse; if it happens to still parse (e.g. truncated exactly at an entry boundary) but is missing entries for images that exist on disk, those images are simply misses — handled the same as "no entry for this source" in the ordinary case, no different code path needed. |
| Manifest parses to something that isn't a mapping of entries (hand-edited into nonsense — a list, a string, `null`) | Same as "fails to parse": treat as absent, cold-cache the directory, rewrite it. |
| An entry is missing a field its `status` requires (e.g. `optimised` with no `lossless`) | Treat that single entry as invalid — re-encode that one source, rewrite that one entry — without discarding the rest of the manifest. This is a stricter, per-entry version of the same posture. |

**Cold-cache-and-continue, not fail-loudly — but reported, not silent.** The explicit argument
for this posture: the cache exists purely as a speed optimisation over behaviour that is already
correct and safe without it (`optimise_image` is pure and deterministic — re-running it always
produces the same result). A missing or corrupt manifest can therefore only cost time, never
correctness: the worst case of "rebuild it" is that this run is as slow as every run was before
this feature existed. Failing the whole `content_save` invocation over a malformed cache
file — a file whose only job is to make a *repeated* run faster — would make a purely
speed-oriented file into a new way for the entire content load to go down, which is a strictly
worse failure mode than the one this feature is trying to fix. A run over a content repository
is also already transactional at the database level (`save_content_to_db` is
`@transaction.atomic`) and `optimise_image` itself famously "must neither abort a run over a
whole content repository nor vanish from it" for a single bad image — the same posture extends
naturally to a single bad cache file.

That said, this repo's conventions are explicit that catching exceptions must name specific
types and must never fail silently. So "recovered from" does not mean "quiet": when a manifest
fails to parse, `content_save` should emit an author-facing line (in the same `click.echo` stream
`_format_image_decision_line` already writes into, so it appears in the same run output the
author is already reading) naming the manifest path and the parse error, exactly as
`validate.py`'s own YAML-error handling already surfaces `yaml.YAMLError` with a location and a
preview rather than swallowing it (see `parse_yaml_file`'s error formatting). The catch clause
should name `yaml.YAMLError` specifically (parse failures) and whatever narrower exception
covers "parsed but wrong shape" (e.g. a `KeyError`/`TypeError`/custom validation raised while
reading required fields out of a parsed entry) — never a bare `except Exception`. The rebuild
itself is silent in the sense that it doesn't stop the run, but it is never silent in the sense
of going unmentioned in the run's own output; an author who committed a half-merged manifest
finds out about it from the very next `content_save` run, not from a mystery slowdown they have
to root-cause later.

---

## 5. Is YAML the right format here?

**Recommendation: YAML**, with several dump-time constraints that close off the ambiguity risks
JSON would sidestep for free.

The case for YAML: it's already the house format for every other content-repository file this
scanner touches (`.yaml`/`.yml` content files, frontmatter), and `get_all_files`/`is_skipped_path`
already treat `_optimised/` as invisible to the content scanner — nothing about adding a manifest
inside it changes how content files are discovered. An author who opens `_optimised/` out of
curiosity is looking at a format they already recognise from every other file in the repo, rather
than the one place in a YAML-authored repository that switches to JSON.

The case against, weighed honestly:

- **Parse cost across hundreds of manifests.** `yaml.safe_load` is measurably slower than
  `json.loads` per call (roughly an order of magnitude on CPython, both being pure-Python-ish
  paths versus JSON's C-accelerated decoder) — but a manifest is one small file per image
  *directory*, not per image, so a "hundreds of images" repository is realistically tens of
  manifests, each a few KB. That cost is negligible next to the ~420ms-per-image encode this
  feature exists to avoid; it would only matter if the format were chosen per-image, which §2
  already ruled out.
- **Ambiguous scalars.** This is the real risk, and it's concrete for this data:
  - A stored filename that is all-digits-and-dots, like a hypothetical `1.2.webp` used as a
    mapping key, is fine as a YAML *key* — YAML mapping keys are read as scalars in a fixed
    position, not type-inferred the way a bare value would be — but the underlying worry is
    real for **values**, and this manifest has one: `source_size`/`stored_size` pairs like
    `[1200, 1600]` parse fine either way (unambiguously a YAML/JSON list), but a hand-edited
    manifest could introduce a `digest` value that "looks numeric" (a hex digest that happens to
    start `0x...` or is all-digits in some hash schemes) or a bare `NO`/`no`/`off`/`on` in a
    filename-derived string, all classic YAML 1.1 boolean/null footguns (`yaml.org` core schema
    treats bare `no`, `off`, `null`, `~` specially). A source file genuinely named `NO.png`
    doesn't appear as a bare scalar anywhere in this format (it's a mapping *key* — see below —
    or embedded inside `original_filename`-shaped strings that should be quoted on principle),
    but any string-typed field derived from a filename is a candidate for this class of bug if
    the dumper doesn't force quoting.
  - PyYAML's default `SafeDumper` already quotes anything that would otherwise be misread as a
    non-string (it quotes `"no"`, `"1.2"`, `"NO.png"`-shaped strings automatically when they're
    plain Python `str` values) — the risk is not "PyYAML gets this wrong" but "a hand-editing
    author gets this wrong," typing an unquoted `no` or `1.2` directly into the file. That's a
    robustness question (§4), not a reason to prefer JSON, since the same hand-editing author
    could equally break JSON's stricter grammar in other ways (trailing commas, unescaped
    backslashes in a Windows-style path fragment).
- **JSON has no equivalent risk** for any of the above, and no comment support either — moot here
  since this file has no author-facing prose to comment on.

**What has to be true of the dump for the ambiguity risk to be closed**, given YAML is chosen:

- **Explicit quoting of string scalars.** Use PyYAML's default `SafeDumper` (or `yaml.safe_dump`)
  un-modified — its default scalar-style resolver already quotes exactly the ambiguous cases
  above. The one thing to actively avoid is adding a custom representer (like `PreservingDumper`
  in `content_save.py`) that overrides this behaviour in the name of readability; §3 already
  rejected `PreservingDumper` for other reasons, and this is a second, independent reason not to
  reach for it here.
- **`sort_keys=True`** — already required for merge-friendliness (§3); also incidentally means
  the file's key order can never itself be read as meaningful (e.g. "most recently added" or
  "processing order"), which closes off one more way a manifest could be misread.
- **No anchors or aliases.** PyYAML's default dumper doesn't introduce these unless the same
  Python object is referenced twice in the data structure being dumped (rare, and easy to avoid
  by constructing a fresh dict per entry rather than sharing sub-structures) — but it's worth
  stating as a constraint because an alias (`*foo`) silently makes one entry's field a *reference*
  to another's, which would be actively dangerous in a file that's supposed to make every entry
  independently readable and independently mergeable (§3's whole point).
- **No flow style** (`default_flow_style=False`), so each entry renders as an indented block
  rather than a `{status: optimised, ...}` one-liner — this is what makes a diff on one field of
  one entry show as a one-line change rather than a whole-entry rewrite, and is standard practice
  in every merge-friendly lockfile examined in §3.

---

## 6. Naming

**Recommendation: keep `manifest.yaml`.**

Working through the considerations raised:

- **Does the name need to repeat "`_optimised`"?** No — the file already sits inside
  `_optimised/`, so its own name doesn't need to re-state that context (`optimised_manifest.yaml`
  would be redundant the same way `images/images_manifest.yaml` would be). `manifest.yaml` reads
  correctly in context: "the manifest, for this `_optimised/` directory."
- **Does it need a leading `_` or `.`?** No — it's already inside a directory the scanner skips
  wholesale (`get_all_files`/`is_skipped_path` both skip everything under a name starting with
  `_` or `.`, recursively), so a second layer of hiding on the manifest's own filename would be
  pure redundancy, adding a rule with no effect for anyone to remember. Leave it a plain name.
- **Is "manifest" already a taken word in this system?** Partially, and worth flagging rather than
  silently reusing. `freedom_ls/accounts/management/commands/build_legal_docs_manifest.py`
  produces a `legal_docs.manifest.json` — described in its own docstring as "a JSON manifest of
  legal-doc git blob SHAs + content," used as an immutable build artifact recording
  `{path: {sha, content}}` pairs, read by `freedom_ls/accounts/legal_docs.py` in place of a live
  git blob read when `.git` isn't present at runtime. That's a different subsystem
  (`accounts`, not `content_engine`), a different format (JSON, not YAML), and a different
  lifecycle (a build-time artifact baked into a read-only image, versus a working-tree file
  meant to be edited by `content_save` and re-committed by the author on their next commit) — but
  it is the same *word*, used for a similar general shape (a small side-file recording per-path
  metadata + a validity fingerprint, standing in for re-deriving that metadata from the source).
  The FLS domain glossary (`.claude/skills/domain-glossary/SKILL.md`) does not list "manifest" as
  a taken word — it isn't a model name or a field name FLS assigns product meaning to, unlike
  "grant", "item", "collection" etc. So this is not a hard collision in the glossary's sense (no
  model or user-facing concept currently means something different by "manifest"), but an author
  or future maintainer who greps the codebase for "manifest" will find both, and should not
  confuse the two — worth a one-line note in whatever the eventual spec/plan says, distinguishing
  "the `_optimised/` cache manifest" from "the legal-docs manifest," since both are now real
  things in this codebase reachable by that bare word.
- **File-naming conventions from `fls-content:conventions`.** That skill's naming rules (`NN. name`
  numbering, `course.md`/`part.yaml`/`form.md`/`content.md` as fixed role-identifying names) are
  about *authored content* files that the scanner walks and that identify a directory's role in
  the course tree. A cache manifest is neither: it's not authored by hand under ordinary use, it's
  not numbered, and it doesn't identify anything about a course/topic/form's role — it's closer in
  spirit to the machine-generated `.gitignore`/`.editorconfig` family of dotfile-adjacent
  bookkeeping than to a content file, even though (per §4) an author will sometimes touch it by
  hand during a merge. None of the numbering/role-file conventions apply, and none suggest a
  different name than the plain, literal `manifest.yaml`.

---

status: ok
