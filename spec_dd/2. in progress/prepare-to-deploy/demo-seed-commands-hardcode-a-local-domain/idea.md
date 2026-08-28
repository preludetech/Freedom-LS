# The demo-seed commands cannot target a real hostname

Source: reviewing `First-Class-LMS` against the First Class infrastructure repo's
`docs/app_repo_contract/` ahead of the first deploy. Generic to any FLS deployment rather than
specific to that fleet, so it belongs here. The concrete project is not working around it. Revised
after that repo shipped `CI-18`, which decides how the first `Site` row on a stack gets written.

## The problem

`create_demo_data` generates synthetic, PII-free data, which is exactly what a public staging tier
needs, since restoring a production dump into one publishes every learner's name and email address.
But it is the only command that writes `Site` rows, and it writes five of them from a hardcoded
list: `Demo` at `127.0.0.1`, `DemoDev` at `127.0.0.1:8000`, then `Bloom`, `Prelude` and `Wrend` on
ports 8001 to 8003. None of those matches a staging hostname, so a staging site cannot be seeded
without editing the command first.

The `qa_helpers` scenario builders are fine, and an earlier version of this note was wrong to say
otherwise. They take a `site_name` argument defaulting to `DemoDev` and resolve it with
`Site.objects.get(name=site_name)`, so they attach to whatever domain that row carries. Fix
`create_demo_data` and they follow for free. That narrows the work to one file.

There is a second problem in the same list, and on a reachable staging tier it is the worse one.
`create_demo_data` creates a superuser per site with the password set equal to the email address, so
seeding staging stands up five administrator accounts whose credentials are in the repo. `CI-18` had
to spell out that a deployment's administrative password is generated and printed once, never a
literal; this command is the counterexample sitting inside FLS.

## Expected fix

Parameterise the site list by domain, defaulting to the current values so local use is unchanged, so
the same command can seed a staging database against its real hostname. An argument is the right
shape rather than an environment read: `HOST_DOMAIN` is one fleet's key name, and a downstream can
pass it on the command line.

Separately, stop `create_demo_data` minting superusers with guessable passwords whenever it is
pointed at a domain that is not a loopback address. Refusing outright is defensible, since the demo
accounts exist for local browsing and a staging tier gets its administrator from the deployment's
own bootstrap command. Generating and printing the password is the other option, and it matches what
`CI-18` settled for the bootstrap case.

Deciding *when* seeding runs relative to a deploy stays the downstream project's business.

## Related

`spec_dd/for_freedom_ls/prepare_to_deploy/create-site-superuser-command-file-is-empty/` is the same
question from the production end: what writes the first `Site` row and the first administrator on a
fresh deployment, and what the credential rules are.

## IMPORTANT

Any new specs to be implemented in the infrastructure repo MUST be saved in spec_dd/for_infra_repo
Any new specs to be implemented in Freedom LS MUST be saved in spec_dd/for_freedom_ls/prepare_to_deploy
