/**
 * Alpine.js CSP-compatible shell components, loaded on every page.
 *
 * The @alpinejs/csp build does not support inline JS expressions.
 * Load this script BEFORE the Alpine CSP script. It is a classic script so
 * visibilityPoller is a global the other component files call.
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
    // Unified side panel (base/_base_interface.html).
    //
    // One <dialog> drives every sidebar in the app (learner course TOC,
    // educator nav, panel_framework nav). The presentation differs per consumer
    // (bottom-sheet vs side-drawer, set via a data attribute) but the mechanism
    // is identical:
    //
    //   - Desktop (lg+): the dialog is opened NON-modally with dialog.show() so
    //     it renders in-flow as a persistent docked column (no inertness, no
    //     scrim) and coexists with the page. Open/closed state persists to
    //     localStorage under data-storage-key (preserving the existing keys).
    //   - Below lg: the dialog is opened with dialog.showModal() so it becomes a
    //     modal overlay with a scrim, an inert background, a focus trap, and
    //     Escape-to-close — all native to <dialog>. showModal() does NOT push a
    //     history entry, so device/browser Back is wired manually (pushState on
    //     open, popstate to close).
    //
    // aria-expanded on the toggle is bound to `open`; the dialog's native
    // "close" event syncs it back and returns focus to the toggle.
    Alpine.data("sidePanel", () => ({
        open: false,
        isMobile: false,
        // Declared here (not just assigned in init()) so each instance owns
        // its own property from the start. Alpine's merge-proxy `set` trap
        // for a nested x-data scope falls back to the nearest ANCESTOR scope
        // that already owns a same-named property when the instance's own
        // scope does not yet have one. A page with a nested sidePanel (e.g.
        // the sidebar wrapping a table's mobile filter/sort sheet) would
        // otherwise have the inner instance's `this.dialog = ...` in init()
        // silently overwrite the outer instance's `dialog`, once the outer
        // instance (which initialises first) had already created that
        // property on itself.
        dialog: null,
        _storageKey: "sidebar",
        _desktopLock: false,
        _mobileOnly: false,
        _mq: null,
        _mqHandler: null,
        _popstateHandler: null,
        _historyPushed: false,
        _closingFromPopstate: false,
        _closingForHtmxNav: false,
        _refocusAfterHtmxNav: false,
        _afterSwapHandler: null,
        triggerEl: null,
        init() {
            // Only this panel's own dialog, never an enclosing panel's. $refs
            // resolves up through ancestor scopes, so a nested panel whose
            // sheet is not rendered (a table toolbar with sort options and no
            // filters) would otherwise adopt the navigation dialog, close it
            // at a breakpoint flip and, being mobile-only, never dock it back.
            // A panel with no dialog of its own has nothing to control.
            this.dialog =
                [...this.$el.querySelectorAll("dialog.side-panel-dialog")].find(
                    (dialog) => dialog.closest("[x-data='sidePanel']") === this.$el,
                ) || null;
            if (!this.dialog) return;
            this._storageKey = this.$el.dataset.storageKey || "sidebar";
            // Player TOC locks the panel open on desktop (no close control).
            this._desktopLock = this.$el.dataset.desktopLock === "true";
            // A mobile-only panel (a table's filter & sort sheet) never docks.
            this._mobileOnly = this.$el.dataset.mobileOnly === "true";
            this._mq = window.matchMedia("(min-width: 1024px)");
            this.isMobile = !this._mq.matches;

            // Position the docked panel below the header bar (consumed by the
            // CSS var on the dialog).
            const top = this.$el.getBoundingClientRect().top;
            this.$el.style.setProperty("--sidebar-top", top + "px");

            // Single point every dismiss route (Escape, scrim, programmatic,
            // Back) funnels through. Unwind the pushed history entry here unless
            // Back is what closed us (in which case the entry is already gone).
            // The close event is queued, not synchronous: a breakpoint flip
            // closes the modal sheet and re-shows the panel docked before
            // this runs, so `open` is read back off the dialog rather than
            // assumed false, or the docked panel would be recorded closed.
            // A sheet closed for an htmx navigation leaves the toggle alone:
            // it sits in the content the response is about to swap out, so
            // focus goes to the new content once the swap lands instead.
            this.dialog.addEventListener("close", () => {
                this.open = this.dialog.open;
                if (this._closingForHtmxNav) {
                    this._refocusAfterHtmxNav = true;
                } else if (this.triggerEl) {
                    this.triggerEl.focus();
                }
                if (this._historyPushed) {
                    this._historyPushed = false;
                    if (!this._closingFromPopstate && !this._closingForHtmxNav) {
                        history.back();
                    }
                    this._closingFromPopstate = false;
                }
                this._closingForHtmxNav = false;
            });
            this.dialog.addEventListener("click", (event) => {
                if (!this.isMobile) return;
                // A click on the dialog element itself (the modal backdrop) closes.
                if (event.target === this.dialog) {
                    this.close();
                    return;
                }
                // A tap on a navigation link inside the sheet: opening the sheet
                // pushed a history entry (so Back dismisses it). If we let the
                // link navigate normally, that entry would stack under the
                // destination and Back from there would replay a phantom
                // "sheet open" view of the page we just left. Replace the pushed
                // entry with the destination instead, so Back goes to the page
                // the learner actually came from. Plain left-clicks only —
                // modified / non-default-target clicks keep native behaviour.
                // Links htmx handles are left to htmx: the htmx:beforeRequest
                // listener below closes the sheet for them, and a replace here
                // would reload the page over the swap htmx already started.
                const link = event.target.closest("a[href]");
                if (
                    !link ||
                    link.closest("[hx-get], [hx-post], [hx-boost='true']") ||
                    event.button !== 0 ||
                    event.metaKey ||
                    event.ctrlKey ||
                    event.shiftKey ||
                    event.altKey ||
                    (link.target && link.target !== "_self")
                ) {
                    return;
                }
                event.preventDefault();
                window.location.replace(link.href);
            });

            // A control inside the sheet that navigates over htmx rather than
            // by link (the organisation switcher's option buttons) never
            // reaches the link branch above, so nothing else dismisses the
            // sheet and it is left covering the content it just loaded.
            // Closing as the request goes out also means the page htmx caches
            // for Back is snapshotted with the sheet already shut.
            //
            // The history entry pushed on open is deliberately left in place.
            // htmx stamps the current entry as its own and caches the outgoing
            // page against it immediately before pushing the new URL, and that
            // entry is what makes Back restore this page. Unwinding it first
            // (history.back() races the in-flight request, and its popstate
            // makes htmx swap the whole document out from under the pending
            // swap) or collapsing htmx's push into a replace (which discards
            // the entry htmx just anchored its snapshot to) both end with Back
            // showing a URL the content no longer matches.
            this.dialog.addEventListener("htmx:beforeRequest", () => {
                if (!this.isMobile || !this.dialog.open) return;
                this._closingForHtmxNav = true;
                this.close();
            });

            // The browser hands focus back to the toggle as the sheet closes,
            // and the swap then detaches that toggle, dropping focus to
            // <body>. Only then is the new content claimed. Focus that some
            // other handler has already placed (a table's own region focus
            // after a sort from its sheet) is left where it is.
            this._afterSwapHandler = () => {
                if (!this._refocusAfterHtmxNav) return;
                this._refocusAfterHtmxNav = false;
                const active = document.activeElement;
                if (active && active !== document.body && active.isConnected) return;
                const main = document.getElementById("main-content");
                if (main) main.focus();
            };
            document.addEventListener("htmx:afterSwap", this._afterSwapHandler);

            // Back closes the modal sheet instead of navigating the page. The
            // entry pushed on open has just been popped, so only close here.
            // Only the mobile sheet ever pushed an entry: the docked panel
            // is left alone, including the one a breakpoint flip has just
            // re-shown while the sheet's own entry is still being unwound.
            this._popstateHandler = () => {
                if (this.dialog.open && this.isMobile) {
                    this._closingFromPopstate = true;
                    this.dialog.close();
                }
            };
            window.addEventListener("popstate", this._popstateHandler);

            // On desktop, default to the persisted state (open if never set);
            // when locked (player TOC) always open and ignore stored state.
            // On mobile, always start collapsed. A mobile-only panel (a
            // table's filter & sort sheet) never opens as a docked panel.
            if (!this.isMobile) this._restoreDesktopState();

            this._mqHandler = (e) => {
                const wasMobile = this.isMobile;
                this.isMobile = !e.matches;
                if (wasMobile === this.isMobile) return;
                // The header's own height is responsive (shorter below the
                // `sm` breakpoint, which this app's 1024px lg cutoff always
                // sits above), so --sidebar-top — set once from it in init()
                // — goes stale across a resize that crosses this
                // breakpoint without a reload. Recapture it here, by which
                // point the header has already re-rendered at its new width.
                const top = this.$el.getBoundingClientRect().top;
                this.$el.style.setProperty("--sidebar-top", top + "px");
                // Reset to the correct mode for the new breakpoint.
                if (this.dialog.open) this.dialog.close();
                this.open = false;
                if (!this.isMobile) this._dockOnceNoModalIsOpen();
            };
            this._mq.addEventListener("change", this._mqHandler);
        },
        destroy() {
            if (this._mq && this._mqHandler) {
                this._mq.removeEventListener("change", this._mqHandler);
            }
            if (this._popstateHandler) {
                window.removeEventListener("popstate", this._popstateHandler);
            }
            if (this._afterSwapHandler) {
                document.removeEventListener("htmx:afterSwap", this._afterSwapHandler);
            }
        },
        _restoreDesktopState() {
            if (this._mobileOnly) return;
            if (this._desktopLock) {
                this._setDesktopOpen(true);
                return;
            }
            const stored = localStorage.getItem(this._storageKey);
            this._setDesktopOpen(stored === null ? true : stored === "true");
        },
        // Every dialog that is shown gets a close watcher, and Escape goes to
        // the newest one. Docking the panel with show() while another
        // dialog is open modally would put the panel's watcher on top, and a
        // non-modal dialog ignores Escape, so the modal could no longer be
        // closed from the keyboard. The page behind a modal is inert anyway,
        // so the panel docks as soon as that modal closes instead.
        _dockOnceNoModalIsOpen() {
            const modal = document.querySelector("dialog:modal");
            if (!modal) {
                this._restoreDesktopState();
                return;
            }
            modal.addEventListener(
                "close",
                () => {
                    if (!this.isMobile && !this.dialog.open) this._restoreDesktopState();
                },
                { once: true },
            );
        },
        _setDesktopOpen(value) {
            this.open = value;
            if (value && !this.dialog.open) {
                const focusedBefore = document.activeElement;
                this.dialog.show();
                this._releaseStolenFocus(focusedBefore);
            } else if (!value && this.dialog.open) {
                this.dialog.close();
            }
        },
        // show() runs the dialog focusing steps, which focus the panel's
        // first control, so a page load would otherwise start keyboard
        // navigation inside the sidebar and the first Tab would skip the
        // site header. Blurring is not enough: the browser's sequential
        // focus starting point stays where focus last was. Focusing <body>
        // (briefly focusable) puts the starting point back at the top of the
        // document, so the first Tab lands on the first control in the page.
        // Focus the reader had already placed somewhere is left alone.
        _releaseStolenFocus(focusedBefore) {
            const active = document.activeElement;
            if (!active || !this.dialog.contains(active)) return;
            if (focusedBefore && focusedBefore !== document.body) {
                focusedBefore.focus({ preventScroll: true });
                return;
            }
            const body = document.body;
            const hadTabindex = body.hasAttribute("tabindex");
            if (!hadTabindex) body.setAttribute("tabindex", "-1");
            body.focus({ preventScroll: true });
            if (!hadTabindex) body.removeAttribute("tabindex");
        },
        toggle(event) {
            if (!this.dialog) return;
            this.triggerEl = (event && event.currentTarget) || null;
            if (this.isMobile) {
                if (this.dialog.open) {
                    this.close();
                } else {
                    this.open = true;
                    this.dialog.showModal();
                    // showModal() pushes no history entry; add one so Back
                    // dismisses the sheet instead of navigating the page.
                    history.pushState({ flsSidePanel: true }, "");
                    this._historyPushed = true;
                }
            } else {
                if (this._desktopLock) return;
                this._setDesktopOpen(!this.open);
                localStorage.setItem(this._storageKey, this.open);
            }
        },
        close() {
            if (!this.dialog) return;
            if (this.dialog.open) this.dialog.close();
            this.open = false;
            if (!this.isMobile) {
                localStorage.setItem(this._storageKey, false);
            }
        },
        // The name the shared close control calls. A side panel holds no
        // unsaved input to guard, so it closes straight away.
        requestClose() {
            this.close();
        },
    }));

    // Polls its own hx-get while the tab is visible (a menu count, a header badge).
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
});
