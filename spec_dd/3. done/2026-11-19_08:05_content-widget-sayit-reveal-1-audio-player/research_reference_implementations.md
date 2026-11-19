# Research: reference implementations of a small "play pronunciation" button

Builds on `spec_dd/1. next/content-widget-sayit-reveal/research_audio_widgets.md` section 1 (not repeated). Provenance: live fetches were thin. Wiktionary, Anki, Forvo and Moodle pages did not document player internals or one-at-a-time behaviour. Where a pattern below is not sourced it is marked "(background / inference)". Verify before relying.

## What was confirmed live

- **MediaWiki TimedMediaHandler (Wikipedia/Wiktionary)**: `[[File:x.ogg]]` renders "a placeholder for a sound file with a play button", inline, or in a pop-up dialog when the file has captions. https://www.mediawiki.org/wiki/Extension:TimedMediaHandler . The markup is a span with class `mw-tmh-player` plus `audio`/`video`. A click loads module `ext.tmh.player.inline`, which swaps in a video.js player (lazy: the heavy player loads on first click, not page load). https://doc.wikimedia.org/TimedMediaHandler/master/js/js/ext.tmh.player.inline.js.html and https://phabricator.wikimedia.org/T246035 . No source found for a one-at-a-time rule. Wiktionary's `{{audio}}` template only emits a caption plus file link, with the player supplied by this extension. https://en.wiktionary.org/wiki/Template:audio
- **MDN `HTMLMediaElement.play()`**: returns a Promise. Rejects with `NotAllowedError` (autoplay or permission policy) or `NotSupportedError` (bad format). A `pause()` or `load()` issued while a play is pending rejects it with `AbortError` (HTML spec, not the MDN page), which is normal and should be ignored. https://developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement/play
- **Anki**: the manual page does not document the `[sound:]` replay button or exclusivity. It does say audio on the front is not replayed on the back unless the field is repeated. https://docs.ankiweb.net/templates/fields.html
- **Moodle**: no documented one-at-a-time mechanism found. Moodle's media filter just wraps mp3/ogg in a player. The generic recipe seen across forums (Qualtrics, Nordcraft, Bubble) is: track the current audio, pause it when another starts. https://community.qualtrics.com/custom-code-12/how-do-i-get-an-audio-clip-to-stop-once-another-clip-is-being-played-9920 and https://forum.nordcraft.com/Prevent-simultaneous-audio-playing . Poodll's "once player" limits play counts, not overlap. https://support.poodll.com/support/solutions/articles/19000084939-making-a-once-player-quiz
- **Media Session API**: not worth using for one-word clips. Chrome only shows media notifications for media of 5 s or more, and several handlers are Chrome-only. https://web.dev/articles/media-session
- **Forvo**: its API demo page returned a redirect to a 404, so nothing was verified. Forvo's public site uses a play-icon link beside each word plus a pre-signed or CDN mp3 URL (background / inference).

## Patterns that recur (the sourced ones plus the standard recipe)

1. **A real control beside the visible word.** Wikipedia/Wiktionary and Forvo show the word or IPA as text, with a small speaker icon next to it. The text is the alternative for 1.2.1. This matches the user's answer: the visible word plus a small speak icon button.
2. **Lazy load.** TimedMediaHandler defers its player until first click. For FLS this means: no `src` fetch before the first press. Create the audio object on first click, or use `preload="none"`.
3. **One at a time, three ways** (inference from the forum recipes):
   - A module-level variable holding the currently playing element. On a play request: `current?.pause()`, set `current` to the new one. Smallest and fits one shared Alpine registration.
   - A capture-phase `play` listener on `document` that pauses every other `<audio>`. Works for native `<audio>` elements, but not for `new Audio()` objects, which are not in the DOM.
   - A single shared `Audio` object that each button re-points (`src = ...; play()`). Guarantees exclusivity, but loses per-button playing state unless the buttons also listen for it, and swapping `src` while a play is pending causes the `AbortError` above.
   A module-level "current" holder, with the other buttons clearing their playing state via `pause`/`ended` events, is the usual choice.
4. **Handle the play promise.** Catch `AbortError` silently (interrupted by another clip), treat `NotAllowedError` as "show nothing, user can press again", and treat `NotSupportedError` or a network error as the failed-load case (see below).
5. **Toggle semantics.** Pressing the button of the clip that is playing either stops it or restarts it. Forum recipes mostly restart, which suits a learner repeating a word. Pick one in the spec and state it. For a pronunciation button, restart-from-start on press is the usual feel, but then the "playing" state needs `aria-pressed` to be avoided (a restart button is not a toggle). Use a changing icon plus a visually-hidden or `aria-live`-free state rather than `aria-pressed` unless it truly toggles.
6. **Reset on end.** Listen to `ended` and `pause` to clear the playing state, otherwise the icon sticks.

## Implications for the spec

- Registration: one Alpine component in `content_engine`'s CSP bundle holding the module-level `current`. Only method and property names in `x-*` attributes.
- Expired signed URL (3600 s): the user chose to refetch on load error. The hook is the media `error` event (or a rejected `play()` with a non-Abort, non-NotAllowed error). A loader-error refetch needs an endpoint or a re-render that yields a fresh signed URL, and a single retry guard to avoid loops. No reference system was found that does this. Moodle, MediaWiki and Forvo use public or long-lived URLs (inference), so this is FLS-specific design.
- `.opus` is not added, so mp3 is the documented format, and `<source type>` can fall back to a type derived from the extension when `mime_type` is empty.
- Do not use the Media Session API.
- Test cases worth writing: press A then B (A stops, A's icon resets); press A twice; press during a pending load; failure then retry; keyboard Enter and Space.

status: ok
