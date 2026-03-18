# Spec driven development

To do this:

## Step 1
1. Make an idea file manually
2. possibly run /improve_idea


## Step 2: make a spec
1. run spec_from_idea
2. Review the spec and adjust manually
3. run spec_review

## Step 2.5: threat model
1. run /threat-model on the spec to identify security considerations
2. Address any gaps in the spec before planning

## Step 3: make a plan

1. run plan_from_spec

This will make a plan and a qa plan.

## Execute the plan

/implement_plan

## Run the Qa

/do_qa

## React to QA report

If there were tests that could not be run because of missing data or similar, then run make_qa_helpers.

If there were bugs detected, run:

TODO

## Security review

Run /security-review before making a PR to check for security issues.

## Make a pr then
/address_pr_review
