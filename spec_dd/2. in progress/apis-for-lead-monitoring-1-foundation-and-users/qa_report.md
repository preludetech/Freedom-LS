# Frontend QA report: apis-for-lead-monitoring-1-foundation-and-users

## Methodology

- Run by hand through Playwright MCP at desktop 1920x1080, mobile 375x812 and tablet 768x1024. The API sections (§2) were run with curl.
- Screenshots were collected into `screenshots/` beside this report. Every image referenced here exists there.
- Pre-step: the branch was rebased (16 commits replayed onto origin/main, no conflicts, lost-change check pass, full tier 11368 passed, pre-commit clean, pushed). The upstream review found the direction unchanged.
- Data reseed: the first load of `/` returned a 500 because `FORCE_SITE_NAME='DemoDev'` matched no Site. The rebase rebuild had recreated the dev DB empty. qa-data-helper seeded it with `create_demo_data --yes` and `content_save demo_content DemoDev`, plus one learner registration. That gives N = 51 users on DemoDev. The smoke gate ran after the seed.

## Diff scoping

- Class: **FULL**.
- Triggering template files:
  - `freedom_ls/api_admin/templates/admin/api_admin/key_issued.html`
  - `freedom_ls/api_admin/templates/admin/api_admin/revoke_confirm.html`
- The rest of the diff is about 75 `.py` and config files under `freedom_ls/api`, `freedom_ls/api_admin`, `freedom_ls/accounts`, `config/`, `pyproject.toml` and `uv.lock`.
- Nothing was skipped: desktop, mobile and tablet all ran.

## Smoke gate

Outcome: **pass**. Pages checked:

- `http://127.0.0.1:8625/`
- `http://127.0.0.1:8625/admin/freedom_ls_api/apikey/`

## Results

Plan sections: §0 Setup, §1 Issue a key, §2 The API from a terminal, §3 Revoke, §4 Audit log, §5 Email verification moves `updated_at`, §6 Side effects of the dependency change.

| Test | Viewport | Status | Note | Screenshot |
|---|---|---|---|---|
| 0.1 | desktop | pass | Branch badge correct, logged in as demodev@email.com, dashboard renders | ![](screenshots/page-2026-11-02T07-42-34-293Z.png) |
| 1.1 | desktop | pass | Empty changelist with "Add API key"; add form has Name, 4 scope checkboxes, Expires at; no Site, key, prefix or hash field | ![](screenshots/page-2026-11-02T07-42-49-232Z.png) ![](screenshots/page-2026-11-02T07-42-42-727Z.png) |
| 1.2 | desktop | fail | No scope: two errors under Scopes (B1). Past expiry correctly rejected | ![](screenshots/page-2026-11-02T07-42-55-567Z.png) ![](screenshots/page-2026-11-02T07-43-32-757Z.png) |
| 1.3 | desktop | pass | "API key issued" page with full key in monospace box, "Copy it now", no flash; browser Back gives ERR_CACHE_MISS | ![](screenshots/page-2026-11-02T07-43-42-317Z.png) |
| 1.4 | desktop | pass | List row correct, secret absent from HTML; change form only Name editable; resubmitting same name issues a different key | ![](screenshots/page-2026-11-02T07-44-00-251Z.png) ![](screenshots/page-2026-11-02T07-44-09-606Z.png) |
| 1.5 | desktop | pass | "QA no users" with Course applications only issued; "Save and continue editing" also lands on key page | none |
| 2.1-2.2 | desktop | pass | curl: missing key gives not_authenticated; all bad keys give identical authentication_failed 401; `?key=` ignored | none |
| 2.3-2.5 | desktop | pass | 51 users, 10 fields, paging, page_size and cursor validation, updated_since validation all as specified | none |
| 2.6 | desktop | pass | Missing scope 403; POST/PUT/PATCH/DELETE 405 JSON; OPTIONS 200; HEAD 200 no body | none |
| 2.7 | desktop | fail | Schema 401/200 lack `Cache-Control: private, no-store` (B2) | none |
| 2.8 | desktop | pass | Last used at updated, Updated at unchanged | ![](screenshots/page-2026-11-02T07-45-51-918Z.png) |
| 2.9 | desktop | pass | Logged-in browser at `/api/v1/users/`: 401 plain JSON, no browsable API | ![](screenshots/page-2026-11-02T07-45-53-853Z.png) |
| 3.1 | desktop | pass | Only "Revoke selected keys" action; confirmation lists 2 keys; revoke works and flash shown; keys then 401 | ![](screenshots/page-2026-11-02T07-46-06-698Z.png) ![](screenshots/page-2026-11-02T07-46-17-475Z.png) |
| 3.2 | desktop | pass | Already-revoked key skipped (1 to revoke, 2 skipped); Cancel leaves list unchanged | ![](screenshots/page-2026-11-02T07-46-27-079Z.png) |
| 3.3 | desktop | fail | Revoke from change page works; revoked key's page still offers Save and writes a history entry (B3) | ![](screenshots/page-2026-11-02T07-46-44-452Z.png) |
| 3.4 | desktop | pass | `/delete/` is 403; status filter Active 0, Expired 0, Revoked 3 | ![](screenshots/page-2026-11-02T07-47-24-485Z.png) |
| 4 | desktop | pass | 3 `api_key.revoked` and 3 `api_key.issued` entries; no secrets; none for skipped re-revoke or no-op Save | ![](screenshots/page-2026-11-02T07-47-45-976Z.png) |
| 1.3-cache | desktop | pass | Add POST answers 200 with `Cache-Control: no-store, max-age=0, no-cache, must-revalidate, private` | none |
| 5 | desktop | pass | Toggling Verified moves `updated_at` as expected; login changes `last_login` only | ![](screenshots/page-2026-11-02T07-48-13-528Z.png) |
| 6 | desktop | pass | Users export has `email_verified` matching the API for all 51 rows; course and topic pages clean; `manage.py check` clean; no "ninja" references | ![](screenshots/page-2026-11-02T07-49-03-417Z.png) |
| 1.1 | mobile | fail | Add form overflows horizontally, scrollWidth 829 in 375 (B4) | ![](screenshots/page-2026-11-02T07-49-33-748Z.png) |
| 1.3 | mobile | pass | Key page fits (375); key wraps; Back button 137x38 | ![](screenshots/page-2026-11-02T07-49-55-857Z.png) |
| 1.4 | mobile | pass | Changelist fits (375); rows stack | ![](screenshots/page-2026-11-02T07-50-01-057Z.png) |
| 3.1 | mobile | pass | Revoke confirmation fits; Cancel link is a small touch target (see notes) | ![](screenshots/page-2026-11-02T07-50-06-735Z.png) |
| 6.2 | mobile | pass | Dashboard, course detail, topic 1 fit at 375, nav and main present, no console errors | ![](screenshots/page-2026-11-02T07-50-20-400Z.png) ![](screenshots/page-2026-11-02T07-50-13-929Z.png) ![](screenshots/page-2026-11-02T07-50-15-728Z.png) |
| 1.1 | tablet | fail | Add form overflows, scrollWidth 829 in 768 (B4) | ![](screenshots/page-2026-11-02T07-50-23-257Z.png) |
| 1.4-3.4 | tablet | pass | Changelist, revoke confirmation and change form fit at 768 | ![](screenshots/page-2026-11-02T07-50-28-132Z.png) ![](screenshots/page-2026-11-02T07-50-30-133Z.png) |
| 3.2-empty | tablet | fail | Confirmation with all keys already revoked shows "To revoke (0)" with enabled Revoke (B5) | ![](screenshots/page-2026-11-02T07-50-41-294Z.png) |
| 6.2 | tablet | pass | Dashboard and topic 1 fit at 768, nav and main present | ![](screenshots/page-2026-11-02T07-50-35-459Z.png) |

## Design check

no design states tested

## Bugs

### B1: No-scope add form shows two errors under Scopes

- Manifestations: 1.2 (desktop).
- Screenshot: ![](screenshots/page-2026-11-02T07-42-55-567Z.png)
- Expected: one error under Scopes: "Choose at least one API scope."
- Actual: "This field is required." and "Choose at least one API scope." both appear. `ApiKeyAddForm.scopes` is a required `MultipleChoiceField` and `ApiKey.clean` (`freedom_ls/api/models.py:54`) also rejects empty scopes.

### B2: Schema endpoint responses lack Cache-Control: private, no-store

- Manifestations: 2.7 (desktop). No screenshot (curl).
- Expected: every API response, `/api/v1/schema/` included, carries `Cache-Control: private, no-store` (spec testing section). Errors are JSON `{detail, code}`.
- Actual: `/api/v1/schema/` 401 and 200 carry no Cache-Control (the 200 has `Vary: Cookie`). The 401 body is pretty-printed `{detail}` with no `code` and Content-Type `application/vnd.oai.openapi+json`.

### B3: Revoked key's read-only change page still saves

- Manifestations: 3.3 (desktop).
- Screenshot: ![](screenshots/page-2026-11-02T07-46-44-452Z.png)
- Expected: a revoked (or expired) key is read-only throughout: no Save buttons and no write to the row.
- Actual: Save, Save and continue editing and Save and add another stay on the page. Save shows "The API key ... was changed successfully.", re-saves the row via `ApiKeyAdmin.save_model` -> `super().save_model`, and writes a "No fields changed." admin history entry.

### B4: API key add form overflows horizontally on mobile and tablet

- Manifestations: 1.1 (mobile), 1.1 (tablet).
- Screenshots: ![](screenshots/page-2026-11-02T07-49-33-748Z.png) ![](screenshots/page-2026-11-02T07-50-23-257Z.png)
- Expected: the add form fits the viewport at 375 and 768 wide, like other admin add forms (the webhook endpoint add form fits at 375).
- Actual: document scrollWidth is 829 at both widths. The "Registrations and progress: LearnerCourseRegistration, CohortCourseRegistration, CourseInterest, CourseProgress" scope checkbox label does not wrap and stretches the fieldset.

### B5: Revoke confirmation with nothing to revoke still offers Revoke and reports "Revoked 0 API keys"

- Manifestations: 3.2-empty (tablet).
- Screenshots: ![](screenshots/page-2026-11-02T07-50-30-133Z.png) ![](screenshots/page-2026-11-02T07-50-41-294Z.png)
- Expected: undecided by the spec. When every selected key is already revoked, the page should not invite a revoke that does nothing and then claim scripts stop at once.
- Actual: "To revoke (0)" with an enabled Revoke button. Submitting shows "Revoked 0 API keys. Scripts using them stop at once." No audit entry is written.

## Bug status

- **FIXED** (commit: 747d55230) — B1: No-scope add form shows two errors under Scopes. Re-verified: only "Choose at least one API scope." appears.
- **FIXED** (commit: 931b4b072) — B2: Schema endpoint responses lack Cache-Control: private, no-store. Decided: every schema response carries `Cache-Control: private, no-store`, and its errors are `{detail, code}` as `application/json`. The 200 keeps the OpenAPI content type.
- **FIXED** (commit: 04c466d07) — B3: Revoked key's read-only change page still saves. Re-verified: a revoked key's change page has no save buttons; an active key keeps the editable Name and all three save buttons.
- **FIXED** (commit: f548c742d) — B4: API key add form overflows horizontally on mobile and tablet. Re-verified: scrollWidth 375 at 375 and 768 at 768. The fix is in shared admin CSS (freedom_ls/site_aware_models/static/site_aware_models/css/admin.css); spot-checks of webhook endpoint add, email address change and API key change pages show no overflow at 375.
- **FIXED** (commit: b211209a5) — B5: Revoke confirmation with nothing to revoke still offers Revoke and reports "Revoked 0 API keys". Decided: the page says "Every selected key is already revoked. Nothing to revoke.", lists the skipped keys, and offers only a Back link. A POST that revokes nothing flashes the warning "No API keys revoked: they were already revoked."

## General notes

Test-plan inaccuracies:

- The key prefix is 16 characters, not 12 as the plan says (the spec says 16).
- 2.2's "same body as 2.1" is loose. The spec gives a missing key (`not_authenticated`) and a bad key (`authentication_failed`) different bodies, and that is what the API does.
- The audit log Action column shows codes (e.g. `api_key.revoked`) for every action, not labels. That admin predates this branch.

Observations that are not bugs:

- The warning triangles on the Expires at inputs are Django's timezone-offset hint (browser UTC+2, server UTC), not an error.
- The Cancel link on the mobile revoke confirmation is a 46x20 text link, a small touch target (nit).
- Browser Back onto the no-store key page gives `net::ERR_CACHE_MISS`, so the key is not replayed from history (good).

Environment and tooling:

- The W001 check line was skipped because `config/settings_dev.py` hard-codes `DEBUG = True`.
- The do_qa command names `.claude/fls-dev/scripts/` wrappers (`qa_cleanup.sh`, `delete_sdd_work_files.sh`, `qa_collect_screenshots.sh`, `compress_screenshots.sh`) that do not exist. The `claude_plugins/sdd/scripts/` copies were used.
- `.claude/fls-dev/config.md` lacks the admin credentials and QA Dev Data sections. The values were read from `.claude/sdd/config.md`.
- The user CSV export downloaded into the screenshot directory and was moved aside.
- The admin user change form (/admin/freedom_ls_accounts/user/<id>/change/) overflows at 375 wide (scrollWidth 427 before the B4 fix, 414 after: the user link and password field). It predates this branch and is not a regression from the fix.
- Extra keys issued during the run: "QA sync 2" (to read the add POST's headers) and "QA mobile" (for the mobile checks).

status: ok · reason: 5 bugs — 3 fixed, 2 unresolved; report rendered, screenshots verified
