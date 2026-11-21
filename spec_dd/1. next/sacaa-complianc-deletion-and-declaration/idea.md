This idea has been cut into 2 specs. Their order, dependencies, the decisions already taken and
the assumptions are in the "SACAA record retention and declarations" section of `spec_dd/1. next/roadmap.md`. Start there.
The text below is the original brief and is kept as written.

# Prevent deletion of user records

We are required to keep records for 5 years.

In admin: dont allow delete. Only dectivate for Users and Learners

Add a "force delete" action to the admin panel for Users and LEarners.  Enter a reason for deletion and confirm.  Make sure it is logged properly.

Have a "last active" timestamp for all users (unless we already have something like that)

No automatic cleanup/housekeeping of inactive users.

# Quiz declaration

A quiz can require the learner to tick a declaration and type their name. FLS stores both with the time and IP address.

display before first page
declaration message configurable
