/**
 * Alpine.js CSP-compatible component registrations for comms.
 *
 * The @alpinejs/csp build does not support inline JS expressions.
 * All Alpine components must be registered via Alpine.data().
 * Load this script BEFORE the Alpine CSP script.
 */

/**
 * A poll timer that stops while the tab is hidden and fires once when it comes
 * back, dispatching a "refresh" DOM event on `target` for its hx-trigger.
 *
 * htmx's own trigger syntax can't express "only while the tab is visible"
 * without an inline filter expression, which the CSP build forbids. The first
 * count already came from the page, so the initial start fires no refresh.
 */
function visibilityPoller(seconds, target) {
    let timer = null;
    const stop = () => {
        if (timer) clearInterval(timer);
        timer = null;
    };
    const refresh = () => target.dispatchEvent(new CustomEvent("refresh"));
    const start = (refreshNow) => {
        stop();
        if (refreshNow) refresh();
        timer = setInterval(refresh, seconds * 1000);
    };
    const onVisibility = () => (document.visibilityState === "visible" ? start(true) : stop());
    document.addEventListener("visibilitychange", onVisibility);
    start(false);
    return {
        destroy() {
            stop();
            document.removeEventListener("visibilitychange", onVisibility);
        },
    };
}

document.addEventListener("alpine:init", () => {
    // Header bell (comms/partials/notification_bell.html).
    //
    // Its badge poll timer comes from visibilityPoller.
    //
    // `open`, `loading` and `failed` also drive the panel: it loads from
    // notification_panel each time it opens (openPanel), not once up front,
    // so the eight rows and the unread count are never stale.
    Alpine.data("notificationBell", () => {
        // A closure, not reactive state: Alpine must not proxy the timer object.
        let poller = null;
        return {
            open: false,
            loading: false,
            failed: false,
            init() {
                poller = visibilityPoller(Number(this.$el.dataset.pollSeconds), this.$refs.badge);

                // Only the panel's own load drives loading/failed. Mark-all and row
                // actions bubble their htmx events up through the same element,
                // and hiding the content for those would lose keyboard focus.
                const content = this.$refs.content;
                const onPanelLoad = (handler) => (event) => {
                    if (event.detail.elt === content) handler();
                };
                content.addEventListener("htmx:beforeRequest", onPanelLoad(() => {
                    this.loading = true;
                }));
                content.addEventListener("htmx:afterSwap", onPanelLoad(() => {
                    this.loading = false;
                }));
                const onFailure = onPanelLoad(() => {
                    this.loading = false;
                    this.failed = true;
                });
                content.addEventListener("htmx:responseError", onFailure);
                content.addEventListener("htmx:sendError", onFailure);
            },
            get contentVisible() {
                return !this.loading && !this.failed;
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
                this.$refs.content.dispatchEvent(new CustomEvent("refresh"));
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
                poller.destroy();
            },
        };
    });

    // The header Messages badge (comms/partials/messages_button.html): polls
    // its own hx-get while the tab is visible.
    Alpine.data("refreshTimer", () => {
        let poller = null;
        return {
            init() {
                poller = visibilityPoller(
                    Number(this.$el.dataset.pollSeconds),
                    this.$refs.target || this.$el,
                );
            },
            destroy() {
                poller.destroy();
            },
        };
    });

    // The thread pane (comms/partials/thread.html).
    //
    // Sizes the pane to the viewport below the site header, so the composer
    // stays in view and the log is the only scrolling part, and opens the log
    // at its newest message. The header's height changes across breakpoints,
    // so the measurement repeats on window resize (bound with x-on:resize.window
    // on the pane, which Alpine removes with the component).
    Alpine.data("conversationThread", () => ({
        init() {
            this.measure();
            this.scrollToLatest();
        },
        measure() {
            const header = document.querySelector("header.header");
            const top = header ? header.getBoundingClientRect().height : 0;
            this.$el.style.setProperty("--thread-top", top + "px");
        },
        scrollToLatest() {
            const log = this.$refs.log;
            log.scrollTop = log.scrollHeight;
        },
    }));
});
