# Research: UX patterns (developer experience) for the fast password hasher

Sources are the repo itself plus general knowledge of pytest-django and Django. No web fetches were made, so there are no URLs to cite.

## Repo conventions found

- `freedom_ls/conftest.py` already pins settings through autouse fixtures that take the `settings` fixture. Examples are `_disable_force_site_name`, `_isolate_media_root` and `_disable_preview_overrides`.
  - Names are underscore-prefixed and snake_case.
  - Each docstring says why the pin exists.
  - `_disable_preview_overrides` ends with "tests that need a preview on opt in via override_settings(...)".
  - That is the precedent for opt-out by setting: autouse default, docstring explains it, and a test overrides the setting.
- Autouse fixtures are the established route for per-test defaults. The suite has no existing autouse fixture that a marker switches off.
- A non-autouse fixture states "Not autouse" in its docstring (`pathless_logo_storage`).
- `pyproject.toml` `[tool.pytest.ini_options]` sets `--strict-markers` and registers every marker in `markers = [...]`. Each entry is a snake_case name plus a "marks tests that ..." description. Examples are `ci_only`, `fls_internal`, `weasyprint`, `dev_tooling` and `needs_fls_host`.
  - An unregistered marker fails at collection, so a typo cannot silently opt a test in or out.
- `config/settings_base.py` sets `PASSWORD_HASHERS` to Argon2 first. `settings_dev` is the pytest settings module (`DJANGO_SETTINGS_MODULE`).
- The `claude_plugins/fls-dev/skills/testing/SKILL.md` skill is the documentation home. It lists the root autouse fixtures (line 63) and has a marker taxonomy section (about line 104). Downstream projects get the fixtures by star-importing the root conftest.
- `freedom_ls/conftest.py` is shipped to downstream projects, so an autouse fixture there is inherited automatically.

## Common patterns

1. **Settings-level override (Django docs, widely used).**
   - Put `PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]` in a test settings module.
   - Discoverable by grepping settings. It is global, with no per-test opt-out except `override_settings` or the `settings` fixture.
   - Here the pytest settings module is `settings_dev`, which also serves QA and dev runs. That could make dev data use the weak hasher, so this is the wrong place.
2. **Autouse fixture using the `settings` fixture.**
   - Matches the repo's existing style.
   - A test opts back in with `settings.PASSWORD_HASHERS = [...]` or `@override_settings(...)`. The fixture runs first, so the test's own override wins.
   - No new concept to learn.
3. **Marker plus an autouse fixture that checks `request.node.get_closest_marker(...)`.**
   - Opt-out reads as a decorator, such as `@pytest.mark.production_password_hashers`. It works at function, class or module level, and `pytestmark` also works.
   - It must be registered in `markers` (strict-markers is already on). It is greppable with `-m production_password_hashers`.
   - Naming should follow the existing snake_case descriptive markers. `production_password_hashers` is consistent in style.
   - One caveat: `-m` filters selection, not behaviour. The marker should not be added to the default `-m 'not ...'` deselection expression.
4. **Opt-in or opt-out fixture requested by name.**
   - Example: `def test_x(production_hashers):`.
   - It is explicit and shows in the signature, but it cannot be applied to a whole class or module without `usefixtures`.
5. **Dedicated hasher test (hybrid).**
   - Tests that verify the production hasher itself (Argon2 identifiers, `check_password` upgrades, `needs_update`) call `make_password(pw, hasher="argon2")` or `get_hasher("argon2")` directly, so no opt-in is needed.
   - Prefer this where possible. It keeps the marker for tests that need the real hash through `User.set_password`.

## Discoverability and documentation

- Put the explanation in the autouse fixture docstring. State what it does, why, and how to opt out, as `_disable_preview_overrides` does.
- Add one line to the testing skill's autouse list at SKILL.md line 63. Add the marker to the marker taxonomy and to the `pyproject.toml` `markers` list.
- Give downstream projects a short note on overriding or disabling it. Two mechanisms are available. The first is the marker, since the downstream conftest imports ours. The second is shadowing the fixture by name in their own conftest, because pytest's nearest-conftest rule lets a same-named fixture override it.
  - Choose a stable, public fixture name for that, rather than an underscore-private one. A private name is a weak contract for downstream use.
- pytest-django itself documents autouse behaviour in the docstring and docs, and its `settings` fixture restores values after each test.

## Surfacing accidental reliance

- A test that asserts a hash string prefix (`argon2$`) or compares to a stored hash fails with an ordinary assertion mismatch. The message does not point at the fast hasher.
  - Mitigation: the marker's description in `pyproject.toml` and the fixture docstring name this failure mode, so a grep on the failure finds them.
- A sanity test, run unmarked, asserts the active first hasher is the fast one. It also asserts that a `production_password_hashers`-marked test sees the production hasher. This makes a silent regression of the switch loud.
- Fast-hasher leakage into production is a separate risk. The switch must live only in a test-only path (the fixture, or test-only settings). It must not live in `settings_base`.
  - A guard test could assert `settings_base.PASSWORD_HASHERS[0]` is still Argon2.

## Recommendation

- Use an autouse fixture in `freedom_ls/conftest.py`, with a leading-underscore name matching its siblings or a public name if downstream shadowing is intended.
- Add the registered marker `production_password_hashers` for opt-back-in.
- Document it in the fixture docstring, the testing skill and the `markers` entry.
- Add a small guard test for each direction.
- Direct hasher-API tests need no marker.

status: ok
