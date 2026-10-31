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

/**
 * Shared by the header bell and the header messages button: one disclosure
 * panel whose content loads each time it opens. Only one header panel is open
 * at a time: opening one announces itself on window and the other closes.
 *
 * Components are built as Object.assign(headerPanel(name), {...}) so the
 * contentVisible getter stays a live getter (an object spread would evaluate
 * it once).
 */
function headerPanel(name) {
    // A closure, not reactive state: Alpine must not proxy the listener.
    let onOtherOpened = null;
    return {
        open: false,
        loading: false,
        failed: false,
        initPanel() {
            const content = this.$refs.content;
            // Only the panel's own content load drives loading/failed. Events
            // bubbling from elements inside the content (row actions) must not
            // flip them: hiding the content for those would lose keyboard focus.
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
            onOtherOpened = (event) => {
                if (event.detail !== name && this.open) this.close();
            };
            window.addEventListener("header-panel-opened", onOtherOpened);
        },
        destroyPanel() {
            window.removeEventListener("header-panel-opened", onOtherOpened);
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
            window.dispatchEvent(new CustomEvent("header-panel-opened", { detail: name }));
            this.$refs.content.dispatchEvent(new CustomEvent("refresh"));
        },
        close() {
            const focusWasInPanel = this.$refs.panel.contains(document.activeElement);
            const focusWasOnTrigger = document.activeElement === this.$refs.trigger;
            this.open = false;
            if (focusWasInPanel || focusWasOnTrigger) {
                this.$refs.trigger.focus();
            }
        },
        // The trigger sits outside the panel, so a click on it counts as a
        // click away. While the panel is still fading out that would close it
        // again straight after the click reopened it; the trigger's own
        // toggle handles that click.
        closeOnClickAway(event) {
            if (this.$refs.trigger.contains(event.target)) return;
            this.close();
        },
        retry() {
            this.openPanel();
        },
    };
}

document.addEventListener("alpine:init", () => {
    // Header bell (comms/partials/notification_bell.html).
    //
    // Its badge poll timer comes from visibilityPoller. The panel loads from
    // notification_panel each time it opens (headerPanel.openPanel), not once
    // up front, so the eight rows and the unread count are never stale.
    Alpine.data("notificationBell", () => {
        // A closure, not reactive state: Alpine must not proxy the timer object.
        let poller = null;
        return Object.assign(headerPanel("notifications"), {
            init() {
                poller = visibilityPoller(Number(this.$el.dataset.pollSeconds), this.$refs.badge);
                this.initPanel();
            },
            destroy() {
                poller.destroy();
                this.destroyPanel();
            },
        });
    });

    // Header messages button (comms/partials/messages_button.html).
    //
    // The panel loads the newest conversations each time it opens. A reply
    // landing while it is open refreshes its rows; closed, the next open
    // loads afresh anyway.
    Alpine.data("messagesPanel", () => {
        let onConversationChanged = null;
        return Object.assign(headerPanel("messages"), {
            init() {
                this.initPanel();
                onConversationChanged = () => {
                    if (this.open) this.$refs.content.dispatchEvent(new CustomEvent("refresh"));
                };
                document.body.addEventListener("conversationChanged", onConversationChanged);
            },
            destroy() {
                document.body.removeEventListener("conversationChanged", onConversationChanged);
                this.destroyPanel();
            },
        });
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

    // The composer form (comms/partials/composer.html).
    //
    // Keeps the hidden "draft" flag at 1 while the box holds text. The thread
    // poll sends the flag so it never swaps out a form with unsent text.
    //
    // Also counts the characters left once the text nears the limit, submits
    // on Ctrl/Cmd+Enter, and offers a retry when the request never reached the
    // server (a refusal is a server reply and shows the server's own alert).
    Alpine.data("messageComposer", () => ({
        maxLength: 0,
        counterFrom: 0,
        length: 0,
        failed: false,
        hint: "Ctrl+Enter to send",
        init() {
            this.maxLength = Number(this.$root.dataset.maxLength);
            this.counterFrom = Number(this.$root.dataset.counterFrom);
            if (/Mac|iPhone|iPad/.test(navigator.platform)) {
                this.hint = "⌘+Enter to send";
            }
            this.onInput();
        },
        get remaining() {
            return Math.abs(this.maxLength - this.length);
        },
        get over() {
            return this.length > this.maxLength;
        },
        get showCounter() {
            return this.length >= this.counterFrom;
        },
        get counterText() {
            if (this.over) {
                return this.remaining + " over the limit";
            }
            return this.remaining + (this.remaining === 1 ? " character left" : " characters left");
        },
        get counterClass() {
            return this.over ? "text-error" : "text-muted";
        },
        onInput() {
            const text = this.$refs.body.value;
            this.length = text.length;
            this.$refs.draft.value = text === "" ? "0" : "1";
        },
        onKeydown(event) {
            if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
                event.preventDefault();
                this.$root.requestSubmit();
            }
        },
        onFailed() {
            this.failed = true;
        },
        onBeforeRequest() {
            this.failed = false;
        },
        retry() {
            htmx.trigger(this.$root, "submit");
        },
        // The form keeps its id, so htmx restores focus itself when a swap
        // replaces it; this covers the out-of-band replacement, which it skips.
        onAfterSettle() {
            if (document.activeElement !== this.$refs.body) {
                this.$refs.body.focus();
            }
        },
    }));

    // The messages page's #thread-pane (comms/thread.html).
    //
    // Sets --thread-top to the site header's height, which the thread and the
    // new-message pane subtract from the viewport so the page itself does not
    // scroll. It sits on the wrapper because htmx swaps what is inside it.
    // The header's height changes across breakpoints, so the measurement
    // repeats on window resize (bound with x-on:resize.window on the wrapper).
    Alpine.data("threadPane", () => ({
        init() {
            this.measure();
        },
        measure() {
            const header = document.querySelector("header.header");
            const top = header ? header.getBoundingClientRect().height : 0;
            this.$el.style.setProperty("--thread-top", top + "px");
        },
    }));

    // The thread pane (comms/partials/thread.html).
    //
    // Keeps the composer in view with the log as the only scrolling part, and
    // opens the log at its newest message.
    //
    // Entries appended by a send or a poll follow the reader only when they
    // were already at the bottom or the entry is their own send; otherwise a
    // "New messages" button counts what arrived below.
    Alpine.data("conversationThread", () => ({
        // The log's scroll position just before earlier messages are
        // prepended, or null when no prepend is in flight.
        beforePrepend: null,
        // The log's last entry just before an append, or undefined when no
        // append is in flight (null is an empty log).
        beforeAppend: undefined,
        atBottom: true,
        newCount: 0,
        reduceMotion: false,
        init() {
            this.reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
            this.scrollToLatest();
            if ("justRead" in this.$el.dataset) {
                this.$dispatch("conversationChanged");
            }
        },
        get hasNew() {
            return this.newCount > 0;
        },
        onScroll() {
            const log = this.$refs.log;
            this.atBottom = log.scrollHeight - log.scrollTop - log.clientHeight <= 48;
            if (this.atBottom) {
                this.newCount = 0;
            }
        },
        showNew() {
            this.scrollToLatest(true);
            this.newCount = 0;
        },
        // Only a swap triggered from the load-earlier control prepends; sends
        // and polls append and should not move the reader.
        rememberScroll(event) {
            const log = this.$refs.log;
            if (event.detail.target !== log) {
                return;
            }
            if (!event.detail.requestConfig.elt.closest("[data-thread-older]")) {
                this.beforeAppend = log.lastElementChild;
                return;
            }
            this.beforePrepend = {
                height: log.scrollHeight,
                top: log.scrollTop,
                logTop: log.getBoundingClientRect().top,
            };
        },
        // Entries after the one that ended the log before the swap are new.
        // Follow them when the reader was at the bottom or sent one; else
        // count the others from the sender as unseen.
        followAppended() {
            if (this.beforeAppend === undefined) {
                return;
            }
            const log = this.$refs.log;
            let entry = this.beforeAppend
                ? this.beforeAppend.nextElementSibling
                : log.firstElementChild;
            this.beforeAppend = undefined;
            let own = false;
            let incoming = 0;
            for (; entry; entry = entry.nextElementSibling) {
                if (entry.hasAttribute("data-own")) {
                    own = true;
                } else {
                    incoming += 1;
                }
            }
            if (this.atBottom || own) {
                this.scrollToLatest(true);
            } else {
                this.newCount += incoming;
            }
        },
        // Prepended entries push the reader's place down by their height, so
        // the scroll offset grows by the same amount to keep it still. The
        // log's own top edge can move too, when the load-earlier control above
        // it disappears on the last page, and the offset follows that as well.
        keepScrollAfterPrepend() {
            this.followAppended();
            if (this.beforePrepend === null) {
                return;
            }
            const log = this.$refs.log;
            log.scrollTop =
                this.beforePrepend.top +
                (log.scrollHeight - this.beforePrepend.height) +
                (log.getBoundingClientRect().top - this.beforePrepend.logTop);
            this.beforePrepend = null;
        },
        // The first scroll on load is instant; later ones glide unless the
        // reader asked for reduced motion.
        scrollToLatest(animate = false) {
            const log = this.$refs.log;
            log.scrollTo({
                top: log.scrollHeight,
                behavior: animate && !this.reduceMotion ? "smooth" : "auto",
            });
        },
    }));
});
