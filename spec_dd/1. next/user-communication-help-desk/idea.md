# Learners should be able to ask for help in course player

The learner should be able to send a message to educators from within the course player so they can ask for help about specific content. Selecting content or asking for help from the course player should put a mesasge in a shared help-desk and then chats can be picked up from there and associated with help tickets

## Context

Split out of `user-communication-ux-improve` (see its `idea.md`, `1. spec.md` and research files in
`spec_dd/2. in progress/user-communication-ux-improve/`, or `spec_dd/3. done/` once it lands).
Constraints its research found:

- Nothing in the codebase is a help desk or a ticket. "Help tickets" have to be defined here.
- A `Conversation` is always between exactly two users, one per pair per site. A request addressed
  to "the educators" has no counterpart until someone picks it up, so the queue needs its own model.
  That model links to a two-person conversation once someone picks the request up.
- `Message` has no field for the course or content item a question is about.
- Educators may only reply to learners they are an educator of (`educators_of`), so the policy has
  to allow whoever picks up a request to answer it.
- `learner_interface` doesn't import `comms` yet. A help control in the player adds that edge.
- `in-app-feedback` puts prompts in the same course-player areas.
