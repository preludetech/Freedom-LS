# Dev email viewer — custom view

## Goal

Give developers and demo presenters an in-browser way to read the emails the
application writes to disk during development, with no new dependencies and no
external service.

## Approach

The development email backend writes each outgoing message as a raw MIME `.log`
file into a local directory. Add a small development-only Django view that:

- lists the message files in that directory (newest first), and
- renders a selected message — subject, from, to, date, and the HTML body shown
  in an isolated frame, with a fallback to the plain-text body.

Messages are parsed with the Python standard library `email` module. No
third-party packages are added.

## Scope

- A development-only view (or pair of views: list + detail).
- Parsing of the on-disk MIME files into displayable fields.
- Rendering the HTML alternative safely in an isolated frame, with a plain-text
  fallback when no HTML part exists.
- A development-only URL entry for the view.
- Documentation of how to open the inbox during a demo.

## Out of scope

- Any change to how or where emails are written in development.
- Any change to production email sending.
- Editing, replying to, deleting, or sending email from the view.

## Acceptance criteria

- The view lists the message files currently on disk, newest first.
- Selecting a message displays its headers and renders its HTML body; messages
  with only a plain-text body still display.
- No new third-party dependency is introduced.
- No external process or binary needs to be started to view emails.
- The view is only available in development.

## Open questions

- How the directory of message files is located (configuration vs convention).
- Whether the view should be reachable by any logged-in user in development or
  restricted further.
- How to handle messages with attachments.
