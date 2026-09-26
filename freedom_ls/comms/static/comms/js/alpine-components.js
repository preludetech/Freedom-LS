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
    // `open`, `loading` and `failed` also drive the panel: it loads from
    // notification_panel each time it opens (openPanel), not once up front,
    // so the eight rows and the unread count are never stale.
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

            this.$refs.panel.addEventListener("htmx:beforeRequest", () => {
                this.loading = true;
            });
            this.$refs.panel.addEventListener("htmx:afterSwap", () => {
                this.loading = false;
            });
            this.$refs.panel.addEventListener("htmx:responseError", () => {
                this.loading = false;
                this.failed = true;
            });
            this.$refs.panel.addEventListener("htmx:sendError", () => {
                this.loading = false;
                this.failed = true;
            });
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
        toggle() {
            if (this.open) {
                this.close();
            } else {
                this.openPanel();
            }
        },
        openPanel() {
            this.open = true;
            this.failed = false;
            this.$refs.panel.dispatchEvent(new CustomEvent("refresh"));
        },
        close() {
            const focusWasInPanel = this.$refs.panel.contains(document.activeElement);
            const focusWasOnBell = document.activeElement === this.$refs.bell;
            this.open = false;
            if (focusWasInPanel || focusWasOnBell) {
                this.$refs.bell.focus();
            }
        },
        retry() {
            this.openPanel();
        },
        destroy() {
            this.stopPolling();
            document.removeEventListener("visibilitychange", this._onVisibility);
        },
    }));
});
