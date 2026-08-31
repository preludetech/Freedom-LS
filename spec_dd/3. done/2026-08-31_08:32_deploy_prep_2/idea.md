The infrastructure repo is at /home/sheena/workspace/first_class/infrastructure

After a review of the infrastructure repo against first class, this plan was created: spec_dd/1. next/deploy_prep_2/notes_from_infrastructrure_repo.md

Implement that plan with the following adjustments:

### FLS-03. The template manifest bootstraps a Site at `127.0.0.1:8000`
- remove the template manifest
- remove all references to the template manifest
We have no use for it

### FLS-04. `.env.example` models several things `ENV-5` and `ENV-6` forbid
Fix this
Make sure claude can edit .env.example (but no other .env or .env.* files)


## Medium

- FLS-09 notify-downstream.yml: Remove this
- FLS-10 `danger_clear_all_course_progress` organise dev-only helpers into a clear location. If they are meant to be used in staging too then have a clear way to turn them on

## Open decision, not a gap
### FLS-14. `AXES_LOCKOUT_PARAMETERS` carries a bare `"username"` rule
Let's keep is as is. Both the username-only rule and `[["ip_address", "username"]]`
