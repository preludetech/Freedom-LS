/**
 * Alpine.js CSP-compatible component registrations for comms.
 *
 * The @alpinejs/csp build does not support inline JS expressions.
 * All Alpine components must be registered via Alpine.data().
 * Load this script BEFORE the Alpine CSP script.
 */

document.addEventListener("alpine:init", () => {
    // Header bell (comms/partials/notification_bell.html).
    //
    // Owns the badge's poll timer: htmx's own trigger syntax can't express
    // "only while the tab is visible" without an inline filter expression,
    // which the CSP build forbids, so the visibility check lives here and
    // triggers the hx-get via a plain DOM event instead.
    //
    // `open`, `loading` and `failed` back the panel added in a later slice;
    // they are declared now so that slice doesn't have to touch this
    // component's shape.
    Alpine.data("notificationBell", () => ({
        open: false,
        loading: false,
        failed: false,
        _timer: null,
        _onVisibility: null,
        init() {
            const seconds = Number(this.$el.dataset.pollSeconds);
            this._onVisibility = () => {
                if (document.visibilityState === "visible") {
                    this.startPolling(seconds, true);
                } else {
                    this.stopPolling();
                }
            };
            document.addEventListener("visibilitychange", this._onVisibility);
            // The first count already came from the page render, so the
            // initial start doesn't also fire an immediate refresh.
            this.startPolling(seconds, false);
        },
        startPolling(seconds, refreshNow) {
            this.stopPolling();
            if (refreshNow) this.refreshBadge();
            this._timer = setInterval(() => this.refreshBadge(), seconds * 1000);
        },
        stopPolling() {
            clearInterval(this._timer);
        },
        refreshBadge() {
            this.$refs.badge.dispatchEvent(new CustomEvent("refresh"));
        },
        destroy() {
            this.stopPolling();
            document.removeEventListener("visibilitychange", this._onVisibility);
        },
    }));
});
