// `error` does not bubble, so the listener runs in the capture phase on the
// document. One listener then covers every avatar, including those htmx
// swaps in later. Removing the image uncovers the initials rendered under it.
document.addEventListener(
    "error",
    function (evt) {
        var target = evt.target;
        if (target instanceof HTMLImageElement && target.hasAttribute("data-profile-picture")) {
            target.remove();
        }
    },
    true
);
