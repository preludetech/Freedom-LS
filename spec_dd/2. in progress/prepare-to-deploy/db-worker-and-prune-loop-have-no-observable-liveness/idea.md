# `db_worker` and the prune loop have no observable liveness

Source: reviewing `First-Class-LMS` against the First Class infrastructure repo's
`docs/app_repo_contract/` ahead of the first deploy. Generic to any FLS deployment rather than
specific to that fleet, so it belongs here. The concrete project is not working around it.

## The problem

Any FLS deployment running the database task backend runs two background processes with no HTTP
surface: `db_worker`, and the housekeeping loop that calls `prune_db_task_results` and, on this
fleet since `COMPOSE-8`, `clearsessions` beside it. Neither can be health-checked. A container
orchestrator sees the process running and calls it healthy, while a wedged worker accepts tasks and
never executes them, which at the point of call looks like success.

The First Class contract requires a healthcheck on both containers and gives no way to write a
meaningful one, because there is nothing in FLS to probe. That is an FLS gap, not a fleet gap: the
same hole exists for any downstream running these commands under Docker, Kubernetes or systemd.

## Expected fix

Have both processes record a heartbeat each time they complete a cycle, either a file mtime under a
configurable path or a row, and ship a way to assert that heartbeat is recent, so a downstream can
wire it to whatever its platform uses for health. The freshness window has to be settable, because
`db_worker` cycles in seconds and a housekeeping loop cycles daily.

Worth deciding upstream rather than downstream: where the heartbeat lives when the container
filesystem is ephemeral and there is no shared volume, and whether the housekeeping loop should be
an FLS management command in its own right rather than a `sh -c 'while true'` wrapper each
downstream writes for itself. That second question got sharper when `COMPOSE-8` put a second command
in the loop. The loop is now a list that grows, and a list that grows in each downstream's compose
file is a list that drifts.

## Related, already filed separately

`spec_dd/for_freedom_ls/site-resolution-native-callers-500/` covers the native
`django.contrib.sites` callers that 500 when no `Site` row matches the request host. The deployment
review confirmed that one from a second direction: it is what makes a first-run bootstrap step
mandatory on a fresh stack. The infra repo has since written that step down as `CI-18`, an
operator-run `setup_initial_prod_data` once per stack, which settles the deploy-sequence half and
leaves the FLS half where it was.

## IMPORTANT

Any new specs to be implemented in the infrastructure repo MUST be saved in spec_dd/for_infra_repo
Any new specs to be implemented in Freedom LS MUST be saved in spec_dd/for_freedom_ls/prepare_to_deploy
