> This idea has been cut into 5 specs. Their order, dependencies, the decisions already taken and
> the assumptions are in the "SACAA content versions and access" section of `spec_dd/1. next/roadmap.md`. Start there.
> The text below is the original brief and is kept as written.

Saving content to the db currently takes in a path, generates uuids and adds everything to the db. We need some safety nets and complience features

# UUIDs

content_save command needs optional parameter --generate-uuids. default False

-  `--generate-uuids` True => uuids should be generated in the content. This is done during content authoring
- False (default) => Raise Exception early if any uuid is missing


# Debug mode

In debug mode: If an organisation is named that does not exist, create it in the db. This will only be used in development. It makes it easier to test the content out locally

# Assume single source

Currently: Content save can be run multiple times, pointing to different directories. Every time we save new things are added. If something was removed from the content directory it is not removed from the database.

Rather:
- When content_save is called for a Site. Assume we are pointing it at ALL of the content for that site.
- content_save currently takes in one path. Upgrade to it can take several (initially we will only have one repo, but this might change)
- Each path should point to a git repo. No uncommitted changes, origin clear.

When content is removed from the source repo: It should not be deleted from the db. It should be marked as "retired" or similar.


# sacaa-requirement Version control
Requirement text: "whenever a question is revised it shall be blocked from the random questions available to the student but, should remain in the system for audit purposes"

We have compliance requirements for questions that change.

1. If we change a question, then the old version should not be served to learners
2. Every time a question or option changes in any way, it counts as a new version. Exact text matching is simple. Will need to store when it changed on system. possibly git hash
3. If a learner answered a question before it was changed, then we need to keep a record of which version of the question they answered

We will need to access:
- question text
- answer option text
- which is the correct answer
- what the learner answered

In the educator interface, we'll need to see what version of the question they answered, and that that question is no longer available

Also consider spec_dd/0. paused/content_snapshots/0. idea.md
It seems overkill. Maybe we can build lightweight versioning into the content engine app in a different way.


# Educator interface new permission for viewing question banks

- Only certain people are allowed to view questions and answers on their courses. When they look we need to log it in the audit log.
- remove question viewing from the admin interface
