# FLS work arising from the First Class deployment review

Source: reviewing `First-Class-LMS` against the First Class infrastructure repo's
`docs/app_repo_contract/` ahead of the first deploy. Two needs came out of it that are generic to
any FLS deployment rather than specific to that fleet, so they belong here rather than in the
concrete project. The concrete project is not working around either.

## 1. `db_worker` and the prune loop have no observable liveness

Any FLS deployment running the database task backend runs two background processes with no HTTP
surface: `db_worker`, and whatever loop calls `prune_db_task_results`. Neither can be
health-checked. A container orchestrator sees the process running and calls it healthy, while a
wedged worker accepts tasks and never executes them, which at the point of call looks like
success.

The First Class contract requires a healthcheck on both containers and gives no way to write a
meaningful one, because there is nothing in FLS to probe. That is an FLS gap, not a fleet gap: the
same hole exists for any downstream running these commands under Docker, Kubernetes or systemd.

**Expected fix.** Have both processes record a heartbeat each time they complete a cycle, either a
file mtime under a configurable path or a row, and ship a way to assert that heartbeat is recent, so a
downstream can wire it to whatever its platform uses for health. The freshness window has to be
settable, because `db_worker` cycles in seconds and a prune loop cycles daily.

Worth deciding upstream rather than downstream: where the heartbeat lives when the container
filesystem is ephemeral and there is no shared volume, and whether the prune loop should be an FLS
management command in its own right rather than a `sh -c 'while true'` wrapper each downstream
writes for itself.

## 2. The demo-seed commands cannot target a real hostname

`create_demo_data` and the `qa_helpers` scenario builders generate synthetic, PII-free data, which
is exactly what a public staging tier needs, since restoring a production dump into one publishes
every learner's name and email address. But every one of them hardcodes a `127.0.0.1:*` domain, so
none can populate a staging site that answers on its own hostname without editing the command
first.

The machinery is right and the constraint is wrong. Any FLS deployment with a publicly reachable
staging tier hits this.

**Expected fix.** Parameterise the demo-seed machinery by site domain, through an argument or an
environment read, defaulting to the current behaviour so local use is unchanged, so the same
commands can seed a staging database against its real hostname. Deciding *when* seeding runs
relative to a deploy stays the downstream project's business.

## Related, already filed separately

`spec_dd/for_freedom_ls/site-resolution-native-callers-500/` covers the native
`django.contrib.sites` callers that 500 when no `Site` row matches the request host. The
deployment review confirmed that one from a second direction: it is what makes a first-run
bootstrap step mandatory on a fresh stack. No new note needed, but the two are the same underlying
issue seen from opposite ends.
