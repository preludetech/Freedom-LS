# Research: codebase (faster-test-runs-3-permission-matrix-test)

Decision taken (answers.md:5-6): one test per capability builds the world once and walks every
role x (kind, relation) cell, failing with a list of every disagreeing (capability, role, kind,
relation); the same treatment for every world-building test in
`freedom_ls/educator_interface/tests/invariants/test_permission_matrix.py` (called "the file" below).

## 0. The file today

- `_build_world(site_a)` at test_permission_matrix.py:506-580 is the only builder. It is called by 9
  tests (lines 600, 643, 662, 700, 787, 802, 818, 834, 850), each once per case.
- `_cases()` (583-592) yields (capability, role, kind, relation) from `CAPABILITY_SCOPE_KINDS`
  (465-496, 30 capabilities) x `RELATIONS_FOR_KIND` (78-83) x `ROLES` (61-68). Idea says 763 cases.
- World-building tests and their parametrization:
  - `test_can_matches_the_matrix` (595-606): 763 cases, one `can()` call each.
  - `test_cohorts_visible_to_agrees_with_can_on_every_cohort` (636-653): 6 cases (per role); already walks the 4 cohort scopes inside the case.
  - `test_learners_visible_to_agrees_with_can_on_every_learner` (656-674): 6 cases, same shape.
  - `test_deactivating_the_staff_member_row_withdraws_the_grant` (688-730): `_gated_true_cases()` (677-685), 67 cases per research_test_timings.md:46.
  - `test_cohort_admin_holds_delete_cohortmembership_on_its_own_cohort` (783-791): 1 case.
  - `test_cohort_admin_holds_add_cohortmembership_on_another_cohort_only_with_a_grant_there` (794-810): 1 case, mutates.
  - `test_the_organisation_import_gate_...` (813-826): 6 cases (per role).
  - `test_the_cohort_import_gate_...` (829-843): 6 cases (per role).
  - `test_the_cohort_import_gate_refuses_an_inactive_cohort` (846-857): 1 case, mutates.
- Tests that do NOT build a world and stay as they are: `test_every_capability_a_role_holds_has_a_matrix_entry` (609), `test_every_matrix_entry_names_every_role` (618), `test_a_roles_permissions_equal_...` (625, 6 cases, no DB), `test_every_capability_reachable_from_the_interface_is_in_matrix` (733), `..._assign_cohort_viewer_is_reachable...` (755), `..._download_cohort_report_is_reachable...` (765, these three build one Organisation and walk the interface), `test_assign_cohort_viewer_is_in_the_matrix` (779).
- Total tests in file now: 763 + 6 + 6 + 67 + 1 + 1 + 6 + 6 + 1 world-building = 857 cases, plus 6 + 1 + 1 + 3 + 1 non-world = 12. Collect to confirm (section 5).

## 1. Mutation and caching

### Which cases mutate data another case would read

Only three mutate, and each already owns its own world, so none needs to share:

1. Deactivation test: `member.is_active = False; member.save(update_fields=["is_active"])`, then back to True (718-726). Mutates `StaffMember` of one user.
2. `test_cohort_admin_holds_add_cohortmembership_on_another_cohort_only_with_a_grant_there`: `assign_object_role(user, other_cohort, "cohort_admin")` (808). Gives cohort_admin a grant on C2, which would turn the `(cohort, OTHER_COHORT)` cell True for cohort_admin on every cohort-scoped capability (and learner cells through membership of L2). It must keep a world of its own (or run last/after restoring with `deactivate_object_role`, but that leaves an extra assignment row and an audit entry; a world of its own is simpler). Do not fold it into the per-capability walk.
3. `test_the_cohort_import_gate_refuses_an_inactive_cohort`: `cohort.is_active = False; cohort.save(...)` (854-855) on C1 and organisation_admin. `can()` ignores the scope's `is_active` (capabilities.py:174-176), so it would not change `can()` answers, but `check_import_gate` reads `cohort.is_active` (learner_import.py:123-124), so the import-gate walk must not see it. Own world, or restore, or mutate a copy; it is one cell so keep it separate or run it after the gate walk with `is_active` restored.

The read-only tests (matrix, two visibility tests, both import-gate tests, the two single-cell reads) can share one world with no restoration.

### The deactivation test against one world

Yes, it can walk all gated-true cells against one world, with state restored. Facts that shape it:

- Every gated role's user has exactly one `StaffMember` row: the `post_save` receiver on `ObjectRoleAssignment` (`freedom_ls/learner_management/signals.py:24-44`) calls `ensure_staff_member(user, organisation)` (learner_management/utils.py:120-125) when `assign_object_role` saves the assignment. For `cohort_admin` and `cohort_viewer` the organisation is C1's, i.e. O1. `StaffMember.objects.get(user=user)` (line 703) relies on that. `site_admin` has no `StaffMember` (and is not in `GATED_ROLES`, 53-59).
- All gated cells for one role depend on that single row, so the walk can toggle once per role (5 toggles) rather than once per cell: deactivate, check every gated-true cell of that role is `False`, check assignment and guardian snapshots equal, reactivate, check every cell `True` again and snapshots equal. That is a stronger economy than "restore after each cell" and still checks every cell both ways.
- Guardian snapshot (`get_perms(user, scope)`, line 712) is per scope; the walk would snapshot per (role, scope) before and after. `get_perms` builds a fresh `ObjectPermissionChecker` per call in django-guardian (verify in the plan; I did not open the installed package), so a mutation between calls is visible.
- Use try/finally (or a fixture teardown) to restore `is_active=True` so a failing assertion in one role does not leave later roles seeing a deactivated row. With per-test rollback it cannot leak out of the test either way.

### Does `can()` cache anything?

No per-user, per-request or per-call cache sits in `can()` or what it calls (capabilities.py:167-200). Each step is a fresh ORM query (`_site_grants(...).exists()`, `_granted_organisations(...).filter(pk=...).exists()`, `_granted_cohorts(...)`, `CohortMembership...exists()`), so a `StaffMember` or `ObjectRoleAssignment` change is seen on the next call. Checked:

- `can()` reads `user.is_authenticated`/`user.is_active`/`user.is_superuser` from the in-memory user (177-181). No test mutates the user object, so reuse is safe. (A future case that deactivates the user would have to refresh it.)
- `roles_granting` -> `get_role_config(site.name)` is `@functools.cache`d by site name (`role_based_permissions/loader.py:52-53`, `clear_caches` at 31-36). It caches the immutable role config, not grants. Within one world it is stable; across tests the conftest does not clear it, and the current per-case tests already rely on that.
- `ContentType.objects.get_for_model` (capabilities.py:114) is Django's process-wide ContentType cache: immutable.
- `_site_of`/`site_of` and `organisation_of` (organisations/utils.py:13-23) read `scope.organisation` through the instance's FK cache; organisation never changes in these tests. The scope instances in the world are reused across cells, which is fine for reads.
- `_current_site` / thread-local request is set by `mock_site_context` -> `site_context` (freedom_ls/tests/site_context.py:15-45), which also clears and seeds `SITE_CACHE`. Held for the whole test, so one world reused across cells is unaffected.
- Guardian rows are written by `assign_object_role` (utils.py:317 `sync_user_object_permissions`) but `can()` never reads them (docstring, capabilities.py:4); only the deactivation test's `get_perms` snapshot does.
- Autouse fixtures clear caches per test, not per cell (`freedom_ls/conftest.py:59-67` clears the Django cache; 131-140, 152, 172, 196 clear policy/backend caches): none relevant to `can()`.

Conclusion: no stale answers from reusing one world across cells after a mutation, provided the mutated `StaffMember` row is re-read by query (as `can()` does) and not held as a cached relation.

## 2. What `_build_world` costs

Per call (lines 506-546):
- `SiteFactory()` x1 (site B) plus the `site` fixture's `SiteFactory` (conftest.py:227-237) once per test. Each new Site also triggers a post_save receiver that creates a default Organisation (organisations/utils.py:26-30 docstring: "Guaranteed to exist by the post_save receiver that gives every Site one"), so two default organisations come with the two sites.
- `OrganisationFactory` x3, `CohortFactory` x4, `LearnerFactory` x4, `CohortMembershipFactory` x4 (each passes an explicit learner, so no extra learner).
- `LearnerFactory` delegates to `ensure_learner` (learner_management/factories.py:44-57) and its `user` SubFactory is `UserFactory`, so 4 users are built there; plus 6 explicit `UserFactory()` calls: 10 users per world.
- Role assignments: 1 `assign_site_role` (utils.py:353-389) and 5 `assign_object_role` (286-320). Each runs `get_or_create` on the assignment, `sync_user_object_permissions` (guardian permission rows) and `_record_role_change` -> `audit_log.record_entry` (audit_log/writer.py:33), i.e. an audit row each (6 total). The receiver (learner_management/signals.py:24-44) creates the `StaffMember` row per object assignment (5 rows: 5 distinct users, O1 each); `assign_site_role` creates none.

Password hashing:
- `UserFactory.password` post-generation (accounts/factories.py:39-46) calls `self.set_password(extracted or self.email)` and `save(update_fields=["password"])`: a hash per user, so 10 hashes per world.
- Hasher in tests: `config/settings_base.py:247-252` lists `Argon2PasswordHasher` first; `config/settings_dev.py` (used by pytest, pyproject.toml:85) sets no `PASSWORD_HASHERS` (grep found none in config/, conftest, pyproject). So tests currently use Argon2. Research timings (research_test_timings.md:22-31) measure the matrix at 66.8s vs 13.3s for 20 cases (Argon2 vs MD5) i.e. about 3.3s vs 0.67s per case.
- `faster-test-runs-1-fast-password-hasher` status: in progress, spec dir `spec_dd/2. in progress/faster-test-runs-1-fast-password-hasher/` holds only idea.md and an untouched todo.md (nothing ticked); no hasher override exists in this worktree. Measure "before" with Argon2 here; the spec should state whether its measurements are taken with or without spec 1 landed (idea.md:7 says about 11 min alone, about 2 min if spec 1 lands first). Spec 1 and this one touch different files: no conflict.

After the change a world is built once per walk test. How many walk tests there will be (about 30 capability tests, if "one test per capability" is parametrized over the 30 capabilities, or one test per capability each building its own world) decides the remaining cost: 30 worlds x (10 hashes + ~60 row inserts). Worth stating in the spec: a per-capability test means 30 world builds, not 1; a single-world alternative would need a module-scoped DB fixture, which pytest-django's rollback does not give (answers.md:5 chose per-test rollback with no state between tests). At 0.67s/world with MD5 that is about 20s for the matrix walk, against about 510s for 763 cases.

## 3. Conventions that bind the change

- `mock_site_context` is mandatory for any test touching site-aware models (claude_plugins/fls-dev/skills/testing/SKILL.md:87-100); every world-building test in the file takes it today. It is not autouse (SKILL.md:63). The `site` fixture it builds on is function-scoped (conftest.py:226-237), so a walk test takes `mock_site_context` and passes it to `_build_world`.
- Markers: the file uses only `@pytest.mark.django_db` and `@pytest.mark.parametrize`; no portability markers (unmarked = portable, SKILL.md:106). Keep it unmarked. `--strict-markers` is on (pyproject.toml:92), so no new marker without registering it.
- Location: `tests/invariants/` is an exempt cross-cutting subpackage (SKILL.md:27); the directory has `__init__.py`. No new directory needed.
- No test counts or lists test ids of this file. Greps for `test_permission_matrix` / `test_can_matches` outside spec docs find only a docstring in `freedom_ls/educator_interface/tests/interface_walk.py:4` and `spec_dd/` research notes; the roadmap names this spec but not its test ids. `.claude/ds/scripts/run_tests.sh` only execs `claude_plugins/django-stack/scripts/run_tests.py`; `[tool.test_tiers]` in pyproject.toml:111-130 selects by path, not by test id. `test_organisation/mirroring_*.txt` are file-level, and the file stays where it is. (I did not read `select_tests.sh` or the test_tiers runner; spec 8 changes the selector, so the plan should confirm no id is hard-coded: grep above says none.)
- `pytest-randomly` is installed (pyproject.toml:68): order is random, so each walk test must be independent. `--dist loadfile` (pyproject.toml:92) already pins the whole file to one xdist worker, so merging parametrized cases into per-capability tests loses no xdist parallelism inside this file.
- `timeout = 300` per test (pyproject.toml:101): a single-world walk is far below that.
- Per `ds`/FLS project rule "no spec reduces what is tested without naming the test that still covers it" (roadmap Decision), the spec must name which test covers each cell and show the cell set is unchanged (assert the walked set equals `_cases()`, or compute the expected count and compare).
- CLAUDE.md: type hints required, no `Any`, no `# type: ignore`; the file already uses `cast(...)` for factory_boy typing (548-551). Failure message must list every disagreement, e.g. collect `(capability, role, kind, relation, expected, actual)` tuples and assert the list is empty with a formatted message.
- Granting in tests: FLS testing skill says use `assign_perm` rather than `assign_object_role` (SKILL.md:47-53) except where role assignments are read, which is the case here (`can()` reads assignments); keep `assign_object_role`.

## 4. Other world-per-case tests the spec should not touch (out of scope, `faster-test-runs-6-prune-slow-tests` territory)

- `freedom_ls/learner_management/tests/scenario_world.py:103` `build_world(site, scale=1)` used by fixtures in `learner_management/tests/conftest.py:12-21`, `learner_management/tests/test_queries.py:98,2652` and `messaging_policy/tests/conftest.py:12-20`, `messaging_policy/tests/test_policy.py:43,119` (the last parametrized by `request.param`).
- Largest parametrized tests per research_test_timings.md:40-46: `form_engine/tests/test_served_paper.py::test_shuffle_with_locks_keeps_locked_items_at_their_index` (1,400 cases), `base/tests/invariants/test_profile_picture_fallback.py::test_no_template_sets_an_inline_onerror_handler` (531), `base/tests/invariants/test_app_templates_use_app_components.py` (485).
- The sibling educator_interface invariants (`test_organisation_isolation.py`, `test_config_authorisation.py`, `test_bulk_run_scoping.py`) share the directory but not `_build_world`; `_build_world` has no other importer (grep on `freedom_ls`).
- Earlier history (informational): `spec_dd/3. done/2026-10-10_11:22_testing-cleanup-junk/research_test_suite_speed.md:44` already flagged this file (0.84-1.05 s per case).

## 5. Measuring before and after

The 55-65s database creation (research_test_timings.md:14-19) dwarfs a quick test run, so report test-body time, not wall time. Run from the worktree root, serial, no coverage, fixed order:

```
uv run pytest freedom_ls/educator_interface/tests/invariants/test_permission_matrix.py -n 0 -p no:randomly --durations=0 --durations-min=0 -q
```

- `-n 0` serial (matches how the research timings were taken); `-p no:randomly` removes random ordering; `--durations=0` lists every setup/call/teardown time, with the sum of the `call` lines (and `setup` lines, which include the `site` fixture) giving test-body time. The pytest summary line's total includes DB creation, so also note the "Using existing/creating test database" overhead, or add `--no-migrations` (3.9s setup per research_test_timings.md:18) for both before and after, stating that it was used.
- Test count before/after: `uv run pytest <file> --collect-only -q | tail -1`. Before should show about 857+12 tests (check); after, about 30 + a handful. Coverage-of-cells proof: after the change, have the walks count the cells they visit and assert the total equals `len(_cases())`, and compare against the pre-change collected count of `test_can_matches_the_matrix` (763) and `test_deactivating_...` (67).
- Run "before" on this branch's base commit (0325aab45 or main) with Argon2, and, if `faster-test-runs-1-fast-password-hasher` lands first, again with its hasher; record both (idea.md:7 expects about 11 min and about 2 min savings).
- The roadmap assumption (roadmap.md:111) requires the report to be against `faster-test-runs/research_test_timings.md`: baseline there is about 3.5s per matrix case x 696 cases (now 763) and 66.8s for 20 cases under Argon2.

## 6. Risks and edge points for the spec

- Failure reporting: a per-capability test loses per-cell test ids; the aggregated assertion message must name (capability, role, kind, relation) and expected vs actual for every disagreement (not stop at the first).
- A walk test that parametrizes over the 30 capabilities keeps a test id per capability; a single test over all capabilities builds one world but gives one failure id. The answers.md says "one test per capability".
- The `can()` result is compared with `is expected` (identity on bool, line 606); keep this so a truthy non-bool return fails.
- The two visibility tests already walk scopes in-case; they can walk roles too and build the world once, as can the two import-gate tests (per-role expectation computed from MATRIX).
- The `test_every_capability_...` tests that call `walk_interface` build their own Organisation: not world-building in the sense of `_build_world`, leave them.

status: ok
