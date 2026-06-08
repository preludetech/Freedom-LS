// If a boosted course-player navigation resolves to a page without the player
// shell (e.g. a deadline-lock redirect to course detail, or a session-expiry
// redirect to login), htmx would have nothing to select for #interface-main and
// would swap empty content. Fall back to a full navigation so the user lands on
// the real page instead of a blank swap. htmx events bubble to document, so
// listening here works regardless of where this script runs.
document.addEventListener("htmx:beforeSwap", function (evt) {
    var target = evt.detail.target;
    if (!target || target.id !== "interface-main") return;
    if (evt.detail.serverResponse.indexOf('id="interface-main"') === -1) {
        evt.detail.shouldSwap = false;
        window.location.href =
            evt.detail.xhr.responseURL || evt.detail.requestConfig.path;
    }
});
