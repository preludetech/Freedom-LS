# Research: reference implementations of permission matrix tests

Question: how do well-known projects test role x permission x object-relation matrices without rebuilding the same data per cell?

Only the GitLab material was checked against fetched search results. The other projects are described from background knowledge and are marked "unverified". Re-check the file paths before citing them in the spec.

## GitLab (verified from docs)

- Shared setup comes from the `test-prof` gem. `let_it_be` and `before_all` build records once per context, inside one transaction rolled back at the end of the group. Per-example `let` and `let!` rebuild per case. GitLab's guide recommends them to cut repeated DB setup: https://docs.gitlab.com/development/testing_guide/best_practices/
- Policy specs sit in `spec/policies/` (and `ee/spec/policies/`). The guide says to give each permission its own `describe` block and not to group several permissions in one, so a failure names the permission: https://docs.gitlab.com/development/permissions/testing_guidelines
- An RSpec helper builds the matrix of project visibility x member access level and asserts allowed or denied in each cell. It uses table syntax (`where(:visibility, :role, :allowed)`). The table is the single source of truth, and the failing row is printed in the example description. Reported in https://gitlab.com/gitlab-org/gitlab/-/issues/389631. That issue also lists what the matrix does not cover: feature flags, other user types such as DeployToken, and attribute checks.
- Caveat: `let_it_be` and `before_all` clash with feature specs that use a separate DB connection (https://gitlab.com/gitlab-org/gitlab/-/issues/578026). This does not apply to pytest-django's in-process rollback.

## Django-world projects (unverified, from memory)

- **django-guardian**: tests use `TestCase` with per-test setup. It has no large matrix and is a poor model for efficiency.
- **django-rules**: tests call predicates directly with in-memory or lightweight objects. Predicates are pure functions, so no DB is needed. This works only if the permission rule can be separated from DB loading.
- **Wagtail** (`wagtail/tests/test_page_permissions.py`, `test_collection_permissions.py`): fixtures loaded once, and `setUpTestData` for users and pages. Many assertions sit in one test method, each checking a user against a page. A failure message names the user and page only through the assertion text.
- **Saleor**: pytest fixtures with a shared permission fixture, and `@pytest.mark.parametrize` over permission lists. Parametrize cost stays low because fixtures are cheap.
- **Sentry**: `TestCase` subclasses with `setUpTestData`-style class setup and fixtures such as `self.create_user` and `self.create_member`. Role scopes are tested by looping over the role and scope sets in one test.
- **Zulip**: `ZulipTestCase` loads a fixed fixture DB cloned once per run. Tests pick named users such as `hamlet` and `iago` for each role instead of building them. A role loop sits in one test, with an `assert_json_error` message naming the case.
- **Discourse, Open edX**: Discourse (RSpec) uses `fab!` (the `let_it_be` equivalent) for shared records. Open edX uses `setUpTestData` and ddt `@data` loops. Both are unverified.

## Patterns that recur

1. **Share setup**: build the world once (`let_it_be`, `setUpTestData`, a named fixture DB, or a module- or class-scoped fixture), with per-test or per-class rollback. Do not rebuild users and cohorts per cell.
2. **Two shapes for the cells**:
   - Parametrized or table-driven separate examples. Each cell is a test id, so the report is exact, but each example carries per-test overhead. This is cheap only if the world is shared.
   - One test per permission or capability that loops over every role x object cell. It is fast, but the plain loop stops at the first failure unless the test collects mismatches.
3. **Failure reporting in a loop**: collect `(permission, role, object, relation, expected, actual)` for every disagreement, then assert the list is empty with a formatted message. This matches the answers file (walk per capability, list every disagreement). Zulip's loops, and `subTest` in Django, use the same idea.
4. **Complete coverage**: the table or loop is generated from the registries (all roles, all permissions, all relations), not hand-written. A guard test asserts the number of cells checked equals the product of the dimensions, or the old case count of 763. This is the way to show "the set of cells is unchanged".
5. **Pure predicates**: django-rules evaluates cheaply because the rule needs no DB. Not an option here, since the spec does not change the rules.

## Implication for this spec

Build the world once per capability test and walk the role x scope cells. Collect every disagreement, and add a guard that the cell count equals the previous 763 parametrized cases. This is the pattern in GitLab (shared setup, one `describe` per permission) and in Zulip and Sentry (role loops over a shared world).

## References

- https://docs.gitlab.com/development/testing_guide/best_practices/
- https://docs.gitlab.com/development/permissions/testing_guidelines
- https://gitlab.com/gitlab-org/gitlab/-/issues/389631
- https://gitlab.com/gitlab-org/gitlab/-/issues/578026
- https://github.com/palantir/test-prof (let_it_be, before_all): background knowledge, not fetched

status: ok · reason: GitLab verified via search; other projects from memory, flagged unverified
