# Idea: the `prod_bucket_setup` upgrade notes describe a system that never shipped

`spec_dd/3. done/2026-08-27_12:32_prod_bucket_setup/upgrade_notes.md` is the document a downstream
project follows to move onto the multi-bucket storage layout. Manual step 3 tells that project to
point the `public` storage alias at `freedom_ls.deployment.storage.OverwritingFileSystemStorage`.
No such class exists. What shipped is the stock `FileSystemStorage` with
`OPTIONS: {"allow_overwrite": True}`.

This fails hard rather than subtly. A `storage=` callable resolves while Django imports the model, so
a project that follows the prose literally gets an `ImportError` on that dotted path the moment
`Organisation` is imported. The project does not boot and the test suite does not collect. The
correct value is not guessable from the notes.

The wrong class is the loudest defect, not the only one. `research_upgrade_notes_claim_audit.md`
checks every claim in the document against the shipped code and finds ten more, in three groups:

- **Two system checks are missing entirely.** The notes describe `freedom_ls_deployment.E001` and
  `E002` as the complete set that `check --deploy` gains. `E003` (a media alias inherited its bucket
  from the shared `AWS_STORAGE_BUCKET_NAME`) and `E004` (an alias holding personal data serves
  unsigned URLs) also exist and are never mentioned. The notes promise five errors on the first
  `check --deploy` of the documented upgrade path. That configuration fires ten, because every alias
  trips `E003` alongside `E001`. A downstream reading only this document believes a clean
  `E001`/`E002` run means it is configured correctly.
- **The document contradicts itself on counts.** It says five per-bucket variables in one sentence
  and six two sentences later; it places "six aliases" on three buckets, which is wrong under every
  reading of "six" the document supports; and it uses three different undefined conventions for how
  many aliases there are. Manual step 3 instructs the reader to declare every alias with no `OPTIONS`
  key, then describes the `public` entry's `OPTIONS` in the next clause.
- **Two claims name the wrong thing.** The exception a missing alias raises is
  `ImproperlyConfigured`, not the `InvalidStorageError` the notes tell the reader to look for.
  `storage_for_alias` catches the latter and re-raises the former with a better message. The
  frontmatter says all five media aliases fail at model import when undeclared; only the three that
  a field actually names do.

## How it got this way

The notes were correct when they were written. `OverwritingFileSystemStorage` was introduced at
10:30 on 2026-08-27, the notes were authored at 10:54, and a PR-review fix deleted the class at 11:18
without touching them. The spec closed at 12:33 and shipped the stale text.

`/update_upgrade_notes` runs about two-thirds of the way through a spec, and the PR-review round
that follows is where most substantive code correction happens. Seven commits landed on this branch
after the notes were authored, and one of them updated the notes. Nothing between authoring and the
move to `spec_dd/3. done/` re-reads the document, so a spec with a long review round is exposed no
matter how carefully its notes were written.

This is not yet a pattern. `research_notes_drift_mechanism.md` spot-checks three other completed
specs and finds no drift in any of them. It is a hole this spec happened to fall through, and the
sibling idea `root-env-example-stale-after-prod-bucket-setup` describes the same hole from the
direction of the root `.env.example`.

## What we are doing

**Correct the notes where they are.** The archived `upgrade_notes.md` is the artifact downstream
projects were pointed at, so it gets fixed in place. Every false claim is corrected, and the `E003`
and `E004` coverage and the real error counts are added, so the document describes what shipped
rather than what was true for the forty-eight minutes the class existed.

**Add a guard that runs while the code is still moving.** A check in the existing pytest suite reads
the `upgrade_notes.md` of any spec under `spec_dd/2. in progress/`, finds the tokens shaped like
Python dotted paths, and resolves each one. It fails when a document names a symbol that does not
exist.

Two things about that guard are settled, both because the incident turns on them:

- It reads the whole document, not just fenced code blocks. Every off-the-shelf markdown-verification
  tool checks fences only, and this document's runnable fence was fine. The bad dotted path was in
  prose. Fence-scoped checking would have missed it.
- A document that deliberately names something gone ("`W001` is deleted; drop it from
  `SILENCED_SYSTEM_CHECKS`") must not fail. That case is real in this very file. The reader marks the
  exception explicitly; nothing infers intent from the surrounding prose, because no prior art
  manages that reliably.

Running inside pytest rather than at worktree-finish is what puts the check in front of the commits
that cause the drift. The commit that deleted this class ran the test suite and passed.

## What this does not cover

The guard catches names that stop resolving. It does not catch manual step 5's other defect. That
step cites `spec_dd/2. in progress/prod_bucket_setup/env_example`, a path that was correct when
written and that the spec's own closure invalidated by moving the directory to `3. done/`. A check
scoped to in-progress specs runs only while that path is still right. Fixing the reference is part of
correcting the document. Catching the class of error is not something this guard does, and the
sibling `.env.example` idea is the better place for it.

`First-Class-LMS` has not applied these notes. It still declares the old two-key `STORAGES` and will
hit the boot failure the notes describe when it pulls. That is the concrete project's work, not this
one's.

## Sources

`research_upgrade_notes_claim_audit.md` checks every claim in the document against the shipped code.
It holds the finding-by-finding table and the list of claims that check out and must not be
disturbed.

`research_notes_drift_mechanism.md` covers where the notes sit in the SDD run order, what
`/update_upgrade_notes` never checks, and which claim classes are mechanically verifiable.

`research_docs_code_drift_practices.md` covers how Django, django-storages, allauth and Wagtail
handle the same risk, which in every case is human review, and why the fence-scoped tooling for
markdown does not fit here.
