SDD is slow and has a bunch of problems.

# Unslop plugin skills, commands, resources

Apply unslop to all
Prefer point lists over long prose.
Add explanation where it is actually necessary or useful, otherwise be concise. don't sacrifice on clarity in order to be concise.

# Reduce artifact size

The different files that come out of the SDD process are huge. make sure they are concise, don't repeat each other, and don't sacrifice clarity in order to be concise.

# QA run

Sometimes the QA plans are too big to be executed in one go. When they are getting bigger then split them up into multiple.

# plan

Currently, when things are planned, then the implementation plan works on things in layers. For example, it'll first do all of the database changes, then all of the admin panel changes, then all of the this, then all of the that.

rather have phases that focus on end-to-end functionality and touch multiple pieces of the stack. For example, if we wanted to expose a new button on the front end, then we would need to update a template, update a view, possibly update a model, possibly update the admin. We would want everything to work at every point in time. We don't want to phase to end with the code tests red.

# testing cleanup

Add a review step that makes use of the testing skill in order to make sure the test code is of good quality.
can delete and combine tests as needed.
