The panel framework has no built-in response for "close the dialog, show a toast, swap nothing".

`changed_response()` in `freedom_ls/panel_framework/actions.py` answers 204. htmx drops a 204's
body, so the out-of-band toast that `HtmxMessagesMiddleware` appends never lands. An empty 200
instead swaps into `#app-modal-body` and reopens the dialog the `closeModal` event just closed.

`RemoveProfilePictureAction.handle_submit` in
`freedom_ls/accounts/panels/personal_details/actions.py` works around this by hand: it answers 200
and sets `HX-Retarget: body` and `HX-Reswap: none`, so only the out-of-band fragments (the toast
and the header avatar) land.

It is the only caller today. When a second confirm action needs a toast after closing, the
framework should offer this response itself: a helper beside `changed_response()`, or a flag on
it, documented in `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`. The
`extract_panels_framework` specs are a natural place to pick it up.
