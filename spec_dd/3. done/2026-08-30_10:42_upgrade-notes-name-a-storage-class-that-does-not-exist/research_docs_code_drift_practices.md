# Research: preventing upgrade/migration docs from naming symbols that don't exist

## 1. Summary

The state of the art splits into two tiers, and there is a real gap between them. Ecosystems that
build their docs (Sphinx, MkDocs, rustdoc) can turn an unresolved cross-reference or a broken code
example into a build failure, but even Sphinx's own `nitpicky` mode only *warns* by default — you
still need `-W`/`SPHINXOPTS=-W` to make it fatal, and CPython and Django both run nitpicky non-fatally
and instead track warning counts by hand
([sphinx-doc/sphinx#3919](https://github.com/sphinx-doc/sphinx/issues/3919),
[python/cpython#101100](https://github.com/python/cpython/issues/101100)). For plain markdown with no
docs build — FLS's situation — the actually-adopted mechanism is narrower and older than any of the
markdown-doctest tooling: extract fenced code blocks (or, more crudely, dotted-path-shaped strings) and
try to execute or import them in a test. Nobody in the Django ecosystem has a general tool that verifies
prose claims like "set `STORAGES` to X"; the closest working prior art is (a) doctest-style runners that
execute fenced *code* blocks, which only catches the problem if the instruction is itself inside a code
block, and (b) small bespoke scripts/tests that regex out dotted paths and `import_string` them. Django
itself does not use any of this for its own release notes — it relies on human review and the
deprecation-timeline process, not automated reference-checking.

## 2. How named projects handle it

**Django itself.** Release notes and the deprecation timeline are hand-written `.txt`/`.rst` files.
Django's own process requires a `.. deprecated::` annotation in the docs, an entry in the current
release notes under "Features deprecated in A.B", and an entry in `docs/internals/deprecation.txt`, but
this is a documentation-authorship checklist, not an automated check
([Django Deprecation Timeline](https://docs.djangoproject.com/en/dev/internals/deprecation/)). The
runtime backstop is `RemovedInDjangoXXWarning`, emitted via `warnings.warn(..., category=...)` at the
code site itself, which catches *code* that still calls a deprecated API, but does nothing for a doc
that merely *names* a symbol that has already been deleted rather than deprecated. Django's Sphinx docs
do run in nitpicky mode in principle (Sphinx supports it), but CPython's own tracking issue
([python/cpython#101100](https://github.com/python/cpython/issues/101100)) shows this is treated as a
warning backlog to whittle down, not a merge gate, and a 2016 regression means nitpicky warnings alone
don't fail a build even with `-W` in some Sphinx versions
([sphinx-doc/sphinx#3919](https://github.com/sphinx-doc/sphinx/issues/3919)).

**django-storages**, the exact surface FLS is documenting (`STORAGES`, Django 4.2's replacement for
`DEFAULT_FILE_STORAGE`/`STATICFILES_STORAGE`), documents the migration in prose with a worked
`STORAGES = {...}` example in its backend docs
([Amazon S3 backend docs](https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html))
and in the Django 4.2 release notes themselves
([Django 4.2 release notes](https://docs.djangoproject.com/en/4.2/releases/4.2/)). Neither ships or
references a check that the dotted `BACKEND` path in the example actually resolves; both rely on the
example being maintained by hand and reviewed by maintainers who know the package.

**django-allauth** ships a hand-maintained `ChangeLog.rst`/upgrade guide
([Upgrade Guide](https://pennersr-django-allauth.mintlify.app/migration/upgrade-guide)) that documents
setting renames (e.g. the `ALLAUTH_TRUSTED_PROXY_COUNT` addition) and view URL renames in prose; no
automated verification was found for this content.

**Wagtail** publishes a per-version "Upgrade considerations" section in its release notes
([Upgrading Wagtail](https://docs.wagtail.org/en/stable/releases/upgrading.html)) and, notably, now also
ships an *agent skill* to help automate applying an upgrade
([An agent skill to upgrade your Wagtail site](https://wagtail.org/blog/an-agent-skill-to-upgrade-your-wagtail-site/)) —
i.e. their newest answer to "will the reader apply this correctly" is to hand the notes to an LLM agent
that runs the actual commands, not to verify the notes' claims ahead of time.

**DRF** publishes release notes as prose on its docs site
([Release Notes](https://www.django-rest-framework.org/community/release-notes/)) with no verification
tooling found either.

Across all four, the pattern is: humans write the migration prose, and the only thing that stops it
from drifting is code review plus (for Django itself) the multi-release deprecation window, which gives
reviewers time to notice a symbol has vanished before the notes about it ship. FLS's failure mode —
deleting the class in the same spec that ships the notes referencing it — is exactly the case this
process is not built to catch, because there is no multi-release gap and no dedicated doc reviewer.

## 3. Mechanisms that make documentation executable or verified

| Mechanism | What it verifies | Cost | Works on loose markdown, no docs build | Maintenance status (as researched) |
|---|---|---|---|---|
| Sphinx `nitpicky` + `nitpick_ignore` ([config docs](https://www.sphinx-doc.org/en/master/usage/configuration.html#confval-nitpicky)) | `:class:`/`:setting:`/etc. cross-references resolve to a known object | Needs a Sphinx build, an object inventory, and `-W`/`SPHINXOPTS=-W` to actually fail CI; even then only warns for missing targets ([#3919](https://github.com/sphinx-doc/sphinx/issues/3919)) | No — requires a Sphinx project and doctree | Core Sphinx feature, actively maintained |
| `doctest` / `pytest --doctest-glob='*.md'` (via `pytest-doctestplus`) | Executes doctest-style `>>>` sessions found in markdown | Needs a real Python interpreter session per example; requires trailing newline inside fences ([pytest-doctestplus](https://pypi.org/project/pytest-doctestplus/)) | Yes, in principle — markdown files, not a docs build | Actively maintained (scientific-python org) |
| `mkdocstrings` / MkDocs `--strict` | API-reference docstrings resolve against real objects; strict mode turns warnings into build failures | Needs an MkDocs site | No — MkDocs site required | Actively maintained, widely used |
| `mktestdocs` | Runs every ` ```python ` fenced block as executable code; asserts inside the block become tests | One `pip install` + one test function per file; only checks code fences, not prose | Yes | Active — latest release found 2025-07-25 ([PyPI](https://pypi.org/project/mktestdocs/)) |
| `phmdoctest` / `pytest-phmdoctest` | Generates a pytest module (or plugin-collected tests) from Python fenced blocks and doctest-style sessions in markdown; supports setup/teardown, skip directives | More setup than mktestdocs; richer feature set (session output matching, project README testing) | Yes | Active — v1.4.0 documented ([phmdoctest](https://tmarktaylor.github.io/phmdoctest/)) |
| `pytest-markdown-docs` | Detects and runs Python fences plus inline docstring-style examples in markdown via a `--markdown-docs` flag | Low — pytest plugin, flag-driven | Yes | Maintained (modal-labs) as of research |
| `pytest-codeblock` | Executes any recognized-language fenced block found by pytest collection | Low | Yes | Documented, no strong signal on active maintenance found |
| Sybil (+ `sybil-extras`) | General doc-testing framework: `PythonCodeBlockParser` executes fenced/`>>>` examples in markdown, RST, etc.; supports "invisible" HTML-comment code blocks for setup boilerplate; framework-agnostic (pytest/unittest) | Moderate — more general/configurable than mktestdocs, has its own parser DSL | Yes | Active — 10.x, `sybil-extras` dated 2026.5.19 ([sybil docs](https://sybil.readthedocs.io/en/latest/markdown.html)) |
| `blacken-docs` | Not a correctness check — reformats Python fences with `black` in place; no `--check`-only mode reported | Low | Yes, but wrong tool for this problem (style, not existence) | Maintained fork under klieret ([blacken-docs](https://github.com/klieret/blacken-docs)) |
| `codeblocks` (shamrin) | Generic extraction of code blocks from markdown for further processing (you supply the checker) | Low — a building block, not a full solution | Yes | Small, low-signal on current maintenance |
| `cargo test --doc` (Rust, comparison point) | Every doc-comment code example *compiles and runs* by default, as a first-class part of `cargo test`; failures block the same test run as unit tests | Built into the toolchain — zero extra tooling, but every example must be valid, runnable Rust (or explicitly marked `no_run`/`ignore`) | N/A — language/toolchain feature | Core `cargo`/`rustdoc` feature ([Cargo Book](https://doc.rust-lang.org/cargo/commands/cargo-test.html)) |
| Custom regex + `import_string` script | Any dotted path that appears in the text, whether or not it's inside a code fence | Cheapest to write, cheapest to run, no dependency; author decides exactly what "looks like a dotted path" | Yes — trivially, since it operates on raw text | N/A — bespoke, no upstream to track |

Key finding for FLS: **every markdown-fence-execution tool (mktestdocs, phmdoctest,
pytest-markdown-docs, pytest-codeblock, Sybil) only protects text that the author put inside a fenced
code block.** The FLS storage-class instruction that caused the incident was prose ("set `STORAGES`
backend to the dotted path `freedom_ls.deployment.storage.OverwritingFileSystemStorage`"), and even
where FLS *does* put things in fences (see `spec_dd/3. done/2026-08-27_12:32_prod_bucket_setup/upgrade_notes.md`,
manual step 2's `build_storages()` example), the dangerous dotted path in that same document
(`OverwritingFileSystemStorage`) appears in manual step 3 as plain prose, not inside the executable
fence. A fence-execution tool would have caught the runnable example in step 2 but not the prose
reference in step 3 — which is exactly the one that was wrong. This materially narrows which mechanisms
are useful here.

## 4. Django-specific name-verification primitives

- **Dotted path importability.** `django.utils.module_loading.import_string(dotted_path)` — Django's
  own function for resolving a `"pkg.mod.ClassName"` string to the object; raises `ImportError` if the
  module path is wrong or the module doesn't define the attribute. This is the exact function Django
  uses internally to resolve `STORAGES[...]["BACKEND"]` strings at runtime, so calling it in a test with
  the literal string copied from a doc is a faithful reproduction of what a downstream project's Django
  boot sequence will do. Source and tests: [`django/utils/module_loading.py`](https://github.com/django/django/blob/main/django/utils/module_loading.py),
  [`tests/utils_tests/test_module_loading.py`](https://github.com/django/django/blob/main/tests/utils_tests/test_module_loading.py).

- **Settings key existence.** No dedicated Django API found beyond plain `hasattr(settings, "KEY")` /
  `getattr(settings, "KEY", sentinel)`, or, for verifying a doc's claim that a project *should* declare a
  key, constructing the value the doc describes (e.g. `build_storages()`'s output) and asserting the
  expected keys are present in the returned dict. No prior-art tool for "does this settings name exist
  in this codebase" was found; it would need a bespoke `hasattr`/dict-key assertion against the actual
  settings-producing code, not the doc.

- **Migration name existence.** `django.db.migrations.loader.MigrationLoader` loads all migration
  files from each app's `migrations/` directory into `loader.disk_migrations`, keyed by `(app_label,
  migration_name)` ([`loader.py`](https://github.com/django/django/blob/main/django/db/migrations/loader.py)).
  A test can instantiate `MigrationLoader(connection)` and assert
  `("freedom_ls_content_engine", "0017_alter_file_file") in loader.disk_migrations` to prove a migration
  name quoted in upgrade notes actually exists on disk. There is a known wrinkle: Django silently
  swallows `ImportError` for bad `MIGRATION_MODULES` entries during `load_disk`
  ([Django ticket #25109](https://code.djangoproject.com/ticket/25109)), so this only proves the
  filename exists, not that it imports cleanly — a separate `import_string`/`import_module` check
  covers that. The third-party `django-test-migrations` package
  ([PyPI](https://pypi.org/project/django-test-migrations/)) adds a *check* (not a doc-verifier) that
  warns about badly-named migrations project-wide; it is a different, broader concern than "does this
  one name in this one doc exist."

- **System check id verification.** Django's documented pattern is integration-style: run
  `django.core.management.call_command("check")` inside a test, wrapped in
  `self.assertRaisesMessage(SystemCheckError, "(app_label.E001) ...")` for error-level checks, or
  capture `stderr` and `assertIn` the message text for warnings (`django.test.SimpleTestCase`,
  `django.core.management.base.SystemCheckError`) — documented at
  [System check framework](https://docs.djangoproject.com/en/5.2/topics/checks/). This proves a check
  id is real by actually triggering the condition it fires under, using `@override_settings` to force
  it. There is **no documented API to enumerate all registered check ids without triggering their
  conditions** — `django.core.checks.registry.registry` holds registered check *functions*, not a
  static list of the ids those functions may emit, since one check function can emit different ids
  under different conditions. So verifying "`freedom_ls_deployment.E002` is a real, currently-emitted
  id" requires reproducing the condition (e.g. an S3-configured-but-DEBUG-off settings override) and
  asserting on the resulting `CheckMessage.id`, mirroring FLS's own existing check tests rather than a
  generic doc-scan.

## 5. The false-positive problem

The recurring failure mode every markdown-doctest tool has to solve is: a doc that deliberately says
"the old `Foo` class no longer exists — stop importing it" must not be flagged as broken, even though
`Foo` genuinely doesn't resolve. Approaches found:

- **Scope to fenced code blocks, not prose.** This is the default posture of every tool in the table
  (mktestdocs, phmdoctest, pytest-markdown-docs, Sybil) — plain sentences are never touched, only
  ` ```python ` (or configured-language) fences are extracted and run. This sidesteps most
  false-positives structurally, at the cost of missing prose-only claims (see §3's finding above, which
  is exactly the FLS incident's shape).
- **Explicit skip markers in HTML comments.** `markdown-doctest` (JS) supports `<!-- skip-example -->`
  immediately before a block that should not be executed
  ([Widdershin/markdown-doctest](https://github.com/Widdershin/markdown-doctest)). Sybil's `SkipParser`
  supports `<!-- skip: start -->` / `<!-- skip: end -->` regions, with optional conditions
  ([Sybil markdown docs](https://sybil.readthedocs.io/en/latest/markdown.html)). phmdoctest similarly
  supports HTML-comment directives to mark blocks as illustrative-only
  ([phmdoctest](https://tmarktaylor.github.io/phmdoctest/)).
- **`no_run`/`ignore` attributes (Rust).** `cargo test --doc` compiles and runs every doc example by
  default; an author who wants to show code that must not execute (or must not even compile — e.g. a
  deliberately-wrong example) annotates the fence with `no_run` or `ignore`
  ([Cargo Book](https://doc.rust-lang.org/cargo/commands/cargo-test.html)). This is the strongest
  version of "opt out, don't opt in" — everything runs unless explicitly excused, which keeps the
  default safe and puts the false-positive burden on a single annotation the author must consciously
  add.
- **`nitpick_ignore` allow-lists (Sphinx).** For references Sphinx can never resolve (e.g. references
  into third-party docs without intersphinx mapping), authors add explicit `(role, target)` tuples to
  `nitpick_ignore` rather than disabling nitpicky mode wholesale
  ([Sphinx config docs](https://www.sphinx-doc.org/en/master/usage/configuration.html#confval-nitpick_ignore)).

No prior art was found for a tool that distinguishes "this symbol is claimed to exist" from "this
symbol is claimed to no longer exist" from surrounding natural-language context (e.g. sentiment/negation
detection) — every mechanism found solves this by requiring the author to mark the exception explicitly
(skip comment, `no_run`, ignore-list entry), never by inferring intent from prose.

## 6. Applicable to FLS / not applicable

FLS's artifacts are plain markdown files under `spec_dd/`, produced by a spec workflow, with no Sphinx
or MkDocs build (confirmed by reading `CLAUDE.md` and
`spec_dd/3. done/2026-08-27_12:32_prod_bucket_setup/upgrade_notes.md`). FLS already runs `pytest` and
pre-commit hooks (`uv run pytest`, and commits go through `uv run git commit` because of pre-commit
hooks per `CLAUDE.md`).

**Not applicable, or applicable only as prior-art reasoning, not adoptable tools:**
- Sphinx `nitpicky`/`nitpick_ignore`/intersphinx — needs a Sphinx build and an object inventory FLS
  does not have and (per "don't build functionality not explicitly requested") should not stand up just
  for this.
- `mkdocstrings`/MkDocs `--strict` — same reasoning; no MkDocs site exists.
- `cargo test --doc` — not applicable; cited only as the strong comparison point ("verification is the
  default, opt-out is explicit") that a lightweight FLS mechanism could aspire to in spirit.
- Full markdown-fence-execution frameworks (Sybil, phmdoctest with its setup/teardown DSL,
  pytest-markdown-docs) — these are real, maintained, would technically run on FLS's loose markdown
  files without a docs build, but they solve a bigger problem (execute example code) than FLS has (verify
  named symbols exist) and would add a dependency and a DSL to learn for a single-file, occasional-spec
  problem. Given "keep recommendations proportionate to a small, single-file problem," these are
  over-scoped for FLS.
- `blacken-docs`/`codeblocks` — wrong axis (formatting/extraction primitives, not existence-checking).

**Applicable, proportionate to a single-file problem:**
- A bespoke, small check — in the spirit of the "Custom regex + `import_string` script" row — that
  scans an `upgrade_notes.md` for text shaped like a Python dotted path (optionally restricted to
  known-prefix namespaces such as `freedom_ls.` and known settings-adjacent contexts like backtick-quoted
  strings following "STORAGES", "BACKEND", etc.) and calls
  `django.utils.module_loading.import_string()` on each candidate inside a `pytest` test, run as part of
  the existing `uv run pytest` suite (not a new pre-commit hook, given the "everything slow runs in
  CI/pytest, not pre-commit" split noted in §2 of this research and the general pre-commit-speed
  argument found at [switowski.com](https://switowski.com/blog/pre-commit-vs-ci/)).
- For migration names specifically: `MigrationLoader(connection).disk_migrations` membership checks,
  per §4, are cheap and exact.
- For system check ids specifically: mirror Django's own documented pattern — a test that triggers the
  condition via `@override_settings` and asserts the id via `SystemCheckError`/`stderr`, per §4 — rather
  than trying to statically enumerate ids, since Django provides no static enumeration API.
- Because scoping to fenced code blocks would have *missed* the actual incident (the bad path was in
  prose, not a fence — see §3), any FLS mechanism should scan the whole document text for dotted-path-
  shaped tokens, not just code fences; this is the one place FLS's answer should diverge from the
  fence-only default every off-the-shelf tool uses. False positives (a doc that says "X no longer
  exists") should be handled the way every prior-art tool handles them — an explicit, opt-in marker
  (e.g. an HTML comment or a fenced block tagged to exclude it) — not inferred from surrounding prose,
  since no prior art does the latter.

## Sources

- [Django Deprecation Timeline](https://docs.djangoproject.com/en/dev/internals/deprecation/)
- [sphinx-doc/sphinx#3919 — nitpicky warnings and -W](https://github.com/sphinx-doc/sphinx/issues/3919)
- [python/cpython#101100 — fix all Sphinx reference warnings](https://github.com/python/cpython/issues/101100)
- [Sphinx configuration — `nitpicky`/`nitpick_ignore`](https://www.sphinx-doc.org/en/master/usage/configuration.html#confval-nitpicky)
- [Django 4.2 release notes](https://docs.djangoproject.com/en/4.2/releases/4.2/)
- [django-storages Amazon S3 backend docs](https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html)
- [django-allauth Upgrade Guide](https://pennersr-django-allauth.mintlify.app/migration/upgrade-guide)
- [Wagtail — Upgrading Wagtail](https://docs.wagtail.org/en/stable/releases/upgrading.html)
- [Wagtail blog — an agent skill to upgrade your Wagtail site](https://wagtail.org/blog/an-agent-skill-to-upgrade-your-wagtail-site/)
- [Django REST framework — Release Notes](https://www.django-rest-framework.org/community/release-notes/)
- [mktestdocs on PyPI](https://pypi.org/project/mktestdocs/)
- [phmdoctest documentation](https://tmarktaylor.github.io/phmdoctest/)
- [pytest-doctestplus on PyPI](https://pypi.org/project/pytest-doctestplus/)
- [pytest-markdown-docs (modal-labs)](https://github.com/modal-labs/pytest-markdown-docs)
- [Sybil — Markdown Parsers](https://sybil.readthedocs.io/en/latest/markdown.html)
- [sybil-extras on PyPI](https://pypi.org/project/sybil-extras/2026.5.19/)
- [blacken-docs (klieret fork)](https://github.com/klieret/blacken-docs)
- [codeblocks (shamrin)](https://github.com/shamrin/codeblocks)
- [markdown-doctest (Widdershin) — skip-example](https://github.com/Widdershin/markdown-doctest)
- [Cargo Book — `cargo test`](https://doc.rust-lang.org/cargo/commands/cargo-test.html)
- [Django — django.utils.module_loading source](https://github.com/django/django/blob/main/django/utils/module_loading.py)
- [Django — test_module_loading.py](https://github.com/django/django/blob/main/tests/utils_tests/test_module_loading.py)
- [Django — django/db/migrations/loader.py](https://github.com/django/django/blob/main/django/db/migrations/loader.py)
- [Django ticket #25109 — MigrationLoader.load_disk hides ImportError](https://code.djangoproject.com/ticket/25109)
- [django-test-migrations on PyPI](https://pypi.org/project/django-test-migrations/)
- [Django — System check framework](https://docs.djangoproject.com/en/5.2/topics/checks/)
- [Django — System checks reference (built-in ids)](https://docs.djangoproject.com/en/5.2/ref/checks/)
- [pre-commit vs. CI (Sebastian Witowski)](https://switowski.com/blog/pre-commit-vs-ci/)

## Not found / no prior art located

- No tool or blog post was found that verifies prose (non-fenced) claims about dotted paths in
  markdown; every executable-markdown tool located operates on fenced code blocks only.
- No Django-ecosystem project was found running any automated existence-check against its own
  release/upgrade notes' code references; all four surveyed projects (Django, django-storages,
  django-allauth, Wagtail) rely on human review.
- No API was found for statically enumerating all system-check ids a registered check function might
  ever emit, without triggering the underlying condition.
- No general prose negation-detection approach ("this symbol is being described as removed, not as
  something to use") was found in any tool; all handle the false-positive problem via explicit opt-in
  markers instead.

status: ok
