# `create_site_superuser.py` is an empty file, so the command silently does not exist

Source: reviewing `First-Class-LMS` against the First Class infrastructure repo's
`docs/app_repo_contract/` ahead of the first deploy. Revised after that repo shipped `CI-18`, which
settles what a first-deploy bootstrap command has to do and hands the job to the app repo.

## The problem

`freedom_ls/site_aware_models/management/commands/create_site_superuser.py` is zero bytes. Django
discovers management commands by walking that directory, and a module with no `Command` class
registers nothing, so `manage.py create_site_superuser` reports an unknown command while the file
sits there looking like the feature exists.

Anyone reading the commands directory to work out how to bootstrap a deployment finds the name and
plans around it. That is what happened here. The First Class infrastructure repo's review of this
project recommended `create_site` and `create_site_superuser` for production setup, and half the
pair does not exist.

Its neighbour `create_site.py` is real, and still not a substitute for the missing half. It takes
`site_name` and `site_domain` with optional `--email` and `--password`, and when they are omitted it
derives the address from the site name and sets the credential equal to that address. Fine for local
work, wrong for anything reachable. It carries a second defect worth fixing in the same pass:
`get_or_create` keys on `name`, so for a site that already exists the command assigns
`site.domain = site_domain` and never calls `save()`. Re-running it to correct a domain prints
nothing and changes nothing.

## What the contract has since settled

`CI-18` in `docs/app_repo_contract/deploy_ci.md` now names the step. A command called
`setup_initial_prod_data`, run by the operator once per stack after `migrate` and
`createcachetable`, writing the rows no migration writes: the `django.contrib.sites` row for the
deployment's hostname, and an administrative account. Three properties bind on it.

- Safe to run twice, because somebody will.
- It never resets a password that already exists. A command that silently rotates a live
  administrator's credential is worse than the gap it closes.
- It generates the password rather than accepting one, and prints it once. That is the whole reason
  the step belongs to a human rather than to CI, since an Actions log keeps what is printed into it.

That is one fleet's clause, but only one thing in it is that fleet's business, namely where the
hostname comes from. The rest is true of every FLS deployment. All of them resolve the tenant by
request host, and all of them start from a database whose only `Site` row is `example.com`.

## What this downstream did

Wrote its own `setup_initial_prod_data` in its own app and called nothing in FLS. Not because the
FLS commands were the wrong shape for the job. `create_site_superuser` is zero bytes and
`create_site` sets the password to the email address, so there was nothing to call.

## Expected fix

Either write the command or delete the file. What is not defensible is an empty module that reads
as an available command from the outside.

Deleting is still the smaller fix and still defensible. `create_site` covers the site row once its
missing `save()` lands, and Django ships `createsuperuser`. Every downstream then writes its own
bootstrap command, which is what this one did anyway.

Writing it is the better fix, because the shape is now known rather than guessed, and `CI-18`
describes it. One change if FLS does ship it: take the domain as a command-line argument rather than
reading an environment variable. `HOST_DOMAIN` is one fleet's key name, and a downstream can pass
`"$HOST_DOMAIN"` on the command line in one line of its runbook. Nothing is gained by teaching the
framework a convention that belongs to whoever deploys it.

If FLS does ship it, do not call it `setup_initial_prod_data`. Django's `get_commands()` builds one
flat name-to-app map by walking `INSTALLED_APPS` in reverse, so the app listed earliest wins and a
duplicate name resolves silently. A downstream that owes its own command of that name, as this one
does, would shadow FLS's or be shadowed by it depending on where the two apps sit in the list, with
nothing printed either way. Give the FLS one a name of its own and let downstreams wrap it.

## Related

`spec_dd/for_freedom_ls/site-resolution-native-callers-500/` covers why a `Site` row matching the
request host is mandatory on a fresh deployment, which is the reason these two commands get reached
for in the first place.

`spec_dd/2. in progress/prepare-to-deploy/` is the downstream work, where the locally-owned
`setup_initial_prod_data` is specified.

## IMPORTANT

Any new specs to be implemented in the infrastructure repo MUST be saved in spec_dd/for_infra_repo
Any new specs to be implemented in Freedom LS MUST be saved in spec_dd/for_freedom_ls/prepare_to_deploy
