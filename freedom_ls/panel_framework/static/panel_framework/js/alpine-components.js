/**
 * Alpine.js CSP-compatible component registrations for panel_framework.
 *
 * Load this script BEFORE the Alpine CSP script and AFTER the base
 * alpine-components.js script.
 */

// Adds a listener and records it alongside its target, type and options, so
// a component's destroy() can remove every listener it registered without
// hand-listing them a second time. options is passed through to both calls
// unchanged (e.g. `true` for a capture-phase listener), since
// removeEventListener only matches a listener registered with the same
// capture flag. Shared by appModal and quickView.
function trackListener(handlers, target, type, handler, options) {
    target.addEventListener(type, handler, options);
    handlers.push([target, type, handler, options]);
}

// Returns focus to whichever element opened a dialog, or to #main-content
// when that element is no longer in the DOM (an htmx navigation that
// followed the same close can remove it). Shared by appModal and quickView.
function focusTriggerOrMain(trigger) {
    if (trigger && document.body.contains(trigger)) {
        trigger.focus();
        return;
    }
    const main = document.getElementById("main-content");
    if (main) main.focus();
}

document.addEventListener("alpine:init", () => {
    // The one shared modal <dialog> (partials/modal_host.html) every panel
    // action's fragment loads into. It sits inside sidePanel's x-data scope
    // (both modal_host and quick_view_host are nested in the wrapper
    // _base_interface.html opens for the sidebar), so every property here
    // is prefixed to avoid a name a nested Alpine scope falls through to:
    // assigning a property an ancestor scope already owns (e.g. a bare
    // "dialog" or "body", which sidePanel and other components also use)
    // overwrites the ancestor's own property instead of shadowing it
    // locally, silently corrupting that component's state.
    Alpine.data("appModal", () => ({
        _trigger: null,
        _handlers: [],
        _snapshot: null,
        dirty: false,
        init() {
            this._dialog = this.$el;
            this._body = document.getElementById("app-modal-body");

            // hx-disabled-elt blurs the trigger before showModal() runs, so
            // native focus return cannot be relied on — the trigger is
            // recorded here instead, while it is still the active element.
            trackListener(this._handlers, document, "htmx:beforeRequest", (event) => {
                if (event.detail.target === this._body && !this._dialog.open) {
                    this._trigger = event.detail.elt;
                }
            });

            // A history restore's swap carries no target in its detail.
            trackListener(this._handlers, document, "htmx:afterSwap", (event) => {
                const target = event.detail.target;
                if (!target) return;
                if (target === this._body) {
                    this._afterBodySwap(event);
                } else if (target.id === "main-content") {
                    // The HX-Location swap is outerHTML, so the pre-swap
                    // target detail still names the now-detached old
                    // element: match on id rather than node identity, since
                    // the live #main-content is a different node by now.
                    this._afterMainContentSwap();
                }
            });

            // A 204 never swaps, so success is only observable as this event.
            trackListener(this._handlers, document.body, "closeModal", () => {
                this._dialog.close();
            });

            trackListener(this._handlers, this._dialog, "close", () => {
                this._body.innerHTML = "";
                const prompt = this._dialog.querySelector("[data-modal-discard-prompt]");
                if (prompt) prompt.hidden = true;
                this._snapshot = null;
                this.dirty = false;
                focusTriggerOrMain(this._trigger);
            });

            // A dirty fragment is one whose form no longer matches the
            // snapshot taken right after it swapped in, so a field edited
            // and then changed back reads clean again.
            trackListener(this._handlers, this._body, "input", () => this._checkDirty());
            trackListener(this._handlers, this._body, "change", () => this._checkDirty());

            // The native "cancel" event fires for both Esc and requestClose(),
            // so this is the single place a dirty form can hold the dialog
            // open. A second Esc pressed before any other user activation
            // cannot be cancelled under the CloseWatcher rules browsers apply
            // to <dialog>: the dialog closes and the typed input is lost.
            // Nothing in this handler can prevent that.
            trackListener(this._handlers, this._dialog, "cancel", (event) => {
                if (!this.dirty) return;
                event.preventDefault();
                this._showDiscardPrompt();
            });

            // A click on the dialog element itself is a backdrop click, only
            // meaningful when the fragment holds no form: a destructive
            // confirmation or read-only content, never something with unsaved
            // input.
            trackListener(this._handlers, this._dialog, "click", (event) => {
                if (event.target === this._dialog && !this._body.querySelector("form")) {
                    this._dialog.close();
                }
            });

            // htmx caches the outgoing page's DOM before pushing the new URL,
            // so an open dialog would otherwise be part of that snapshot and
            // reopen on Back.
            trackListener(this._handlers, document, "htmx:beforeHistorySave", () => {
                if (this._dialog.open) this._dialog.close();
            });
        },
        destroy() {
            this._handlers.forEach(([target, type, handler, options]) => {
                target.removeEventListener(type, handler, options);
            });
        },
        requestClose() {
            if (typeof this._dialog.requestClose === "function") {
                this._dialog.requestClose();
            } else {
                this._dialog.close();
            }
        },
        // Hides the discard prompt without closing the dialog. Called from
        // the prompt's "Keep editing" button.
        keepEditing() {
            const prompt = this._dialog.querySelector("[data-modal-discard-prompt]");
            if (prompt) prompt.hidden = true;
            const form = this._body.querySelector("form");
            const field = form && form.querySelector("input, select, textarea");
            if (field) field.focus();
        },
        // The only caller of close() from a button: the prompt has already
        // confirmed the loss of unsaved input, so no further guard applies.
        discard() {
            this._dialog.close();
        },
        _afterBodySwap(event) {
            // A fresh snapshot for every fragment that lands in the body,
            // whether this is the initial open, a "save and add another"
            // re-render or a 422: the guard always compares against what is
            // on screen right now, not what was there before.
            this._snapshotForm();
            if (!this._dialog.open) {
                // The fragment is already in the DOM, so native autofocus
                // picks the initial focus.
                this._dialog.showModal();
                return;
            }
            if (event.detail.xhr.status === 422) {
                const target =
                    this._body.querySelector("[data-error-summary]") ||
                    this._body.querySelector('[aria-invalid="true"]');
                if (target) target.focus();
                return;
            }
            const field = this._body.querySelector("[autofocus]");
            if (field) field.focus();
        },
        _afterMainContentSwap() {
            // htmx handles HX-Trigger before HX-Location: closeModal already
            // focused the trigger by the time this swap removes it from the
            // DOM, which drops focus to <body>. Only then does this claim it.
            if (this._trigger && document.activeElement === document.body) {
                document.getElementById("main-content").focus();
            }
            this._trigger = null;
        },
        _snapshotForm() {
            const form = this._body.querySelector("form");
            this._snapshot = form ? new FormData(form) : null;
            this.dirty = false;
        },
        _checkDirty() {
            const form = this._body.querySelector("form");
            this.dirty = form !== null && this._serialiseForm(new FormData(form)) !== this._serialiseForm(this._snapshot);
        },
        // Both FormData objects come from the same form element, so their
        // entries() order is stable and the joined pairs are safe to compare
        // as strings.
        _serialiseForm(formData) {
            if (!formData) return "";
            return Array.from(formData.entries())
                .map(([name, value]) => `${name}=${value}`)
                .join("&");
        },
        _showDiscardPrompt() {
            const prompt = this._dialog.querySelector("[data-modal-discard-prompt]");
            if (!prompt) return;
            prompt.hidden = false;
            const keepEditingButton = prompt.querySelector("[autofocus]");
            if (keepEditingButton) keepEditingButton.focus();
        },
    }));

    // The drawer (partials/quick_view_host.html) a row's quick-view trigger
    // loads into. It sits inside sidePanel's x-data scope alongside appModal
    // (both are siblings under _base_interface.html's sidebar wrapper), so —
    // for the same reason appModal's own state is prefixed — every name here
    // is one neither sidePanel nor appModal already owns. That has to hold
    // even for a name each of them only assigns inside init() rather than
    // declaring up front (as appModal's own _dialog and _body do): Alpine
    // resolves an as-yet-undeclared "this.x = …" against the whole scope
    // chain, so appModal's and quickView's _open() ended up sharing one
    // dialog reference — whichever component's init() ran last — until each
    // of _dialog/_body/_trigger/_handlers below got its own "qv" name.
    Alpine.data("quickView", () => ({
        _isMobile: false,
        _qvTrigger: null,
        _shownUrl: null,
        _stale: false,
        _entityId: null,
        _refreshHandlers: [],
        _lastUrl: null,
        _qvHandlers: [],
        _qvMq: null,
        _qvHistoryPushed: false,
        _qvClosingFromPopstate: false,
        _qvClosingForBreakpoint: false,
        _qvSkipHistoryUnwind: false,
        init() {
            this._qvDialog = this.$el;
            this._qvBody = document.getElementById("quick-view-body");
            this._title = document.getElementById("quick-view-title");
            this._openLink = document.getElementById("quick-view-open");
            this._status = document.getElementById("quick-view-status");
            this._skeletonTemplate = this._qvDialog.querySelector(
                "[data-quick-view-skeleton]",
            );
            this._errorTemplate = this._qvDialog.querySelector("[data-quick-view-error]");
            this._qvMq = window.matchMedia("(min-width: 768px)");
            this._isMobile = !this._qvMq.matches;

            // htmx only leaves modifier-key clicks alone on boosted anchors.
            // This trigger is a plain hx-get anchor, so without this it would
            // still be intercepted; capture phase gets in ahead of htmx's own
            // (bubble-phase) click listener so the browser follows the
            // trigger's href natively instead.
            trackListener(
                this._qvHandlers,
                document,
                "click",
                (event) => {
                    if (!event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
                        return;
                    }
                    if (event.target.closest('[aria-controls="quick-view"]')) {
                        event.stopPropagation();
                    }
                },
                true,
            );

            trackListener(this._qvHandlers, document, "htmx:confirm", (event) => {
                const trigger = event.detail.elt;
                if (!trigger || !trigger.matches('[aria-controls="quick-view"]')) return;
                const url = event.detail.path;
                if (url === this._shownUrl && this._qvDialog.open) {
                    event.preventDefault();
                    this._close();
                    return;
                }
                if (url === this._shownUrl && !this._stale) {
                    event.preventDefault();
                    this._open(trigger);
                    return;
                }
                this._open(trigger);
                this._startLoading(trigger, url);
            });

            trackListener(this._qvHandlers, document, "htmx:afterSwap", (event) => {
                if (event.detail.target === this._qvBody) {
                    this._afterBodySwap(event);
                }
                // Any swap can recreate a trigger (e.g. a table refetch), so
                // this runs unconditionally rather than only for the body.
                this._syncExpanded();
            });

            trackListener(this._qvHandlers, document, "htmx:responseError", (event) =>
                this._handleBodyError(event),
            );
            trackListener(this._qvHandlers, document, "htmx:sendError", (event) =>
                this._handleBodyError(event),
            );

            // Single point every dismiss route (Esc, requestClose(), Back, a
            // breakpoint flip) funnels through. A mobile open pushed one
            // history entry so Back would dismiss the sheet rather than
            // navigate the page; unwind it here unless Back is what closed
            // us (its entry is already gone), a breakpoint flip is about to
            // reopen in the other mode, or the caller asked to leave the
            // pushed entry alone (followOpenLink is about to replace it).
            // A breakpoint flip's close is not a real dismissal, so it must
            // leave _qvHistoryPushed exactly as it found it: the entry (if
            // any) is still sitting in history, just not the one currently
            // open, and _showDialog() below relies on that flag staying
            // true to avoid pushing a second one when mobile mode returns.
            trackListener(this._qvHandlers, this._qvDialog, "close", () => {
                this._syncExpanded();
                focusTriggerOrMain(this._qvTrigger);
                if (
                    this._qvHistoryPushed &&
                    !this._qvSkipHistoryUnwind &&
                    !this._qvClosingForBreakpoint
                ) {
                    this._qvHistoryPushed = false;
                    if (!this._qvClosingFromPopstate) {
                        history.back();
                    }
                }
                this._qvClosingFromPopstate = false;
                this._qvClosingForBreakpoint = false;
                this._qvSkipHistoryUnwind = false;
            });

            // showModal() gives the mobile sheet native Esc-to-close; show()
            // gives the desktop drawer none, so this covers that case only,
            // and steps aside when some other dialog (e.g. #app-modal) is
            // the one currently in the top layer, or when some other layer
            // above the drawer (e.g. an open dropdown menu) already
            // consumed this Escape via preventDefault(). That layer's own
            // handler has to run first for this check to see it: this
            // listener stays on the bubble phase, and a capture-phase
            // Escape handler (dropdown-menu.html's onEscape) always
            // finishes before any bubble-phase listener runs, whatever
            // order the two components happened to initialise in.
            trackListener(this._qvHandlers, document, "keydown", (event) => {
                if (event.key !== "Escape") return;
                if (!this._qvDialog.open || this._isMobile) return;
                if (document.querySelector("dialog[open]:modal")) return;
                if (event.defaultPrevented) return;
                this._close();
            });

            // Crossing the md breakpoint while open has to reopen in the
            // other mode (modal below md, docked at and above it), which
            // only takes effect through a fresh show()/showModal() call.
            // The close this triggers is not a real dismissal, so it must
            // not run the history unwind above.
            trackListener(this._qvHandlers, this._qvMq, "change", (event) => {
                const wasMobile = this._isMobile;
                this._isMobile = !event.matches;
                if (wasMobile === this._isMobile || !this._qvDialog.open) return;
                this._qvClosingForBreakpoint = true;
                this._qvDialog.close();
                this._showDialog();
                this._syncExpanded();
            });

            // showModal() pushes no history entry of its own, so Back would
            // otherwise navigate the page instead of dismissing the sheet.
            trackListener(this._qvHandlers, window, "popstate", () => {
                if (this._qvDialog.open) {
                    this._qvClosingFromPopstate = true;
                    this._qvDialog.close();
                }
            });

            // htmx caches the outgoing page's DOM before pushing the new
            // URL, so an open drawer would otherwise be part of that
            // snapshot and reopen on Back. The mobile drawer's pushed
            // history entry is unwound by the close handler above, the same
            // way #app-modal's is. Nothing in this app navigates over htmx
            // from inside the quick view itself, so the race sidePanel's
            // htmx:beforeRequest guard exists for (an in-flight push racing
            // a history.back()) cannot happen here.
            trackListener(this._qvHandlers, document, "htmx:beforeHistorySave", () => {
                if (this._qvDialog.open) this._qvDialog.close();
            });
        },
        destroy() {
            this._qvHandlers.forEach(([target, type, handler, options]) => {
                target.removeEventListener(type, handler, options);
            });
            this._refreshHandlers.forEach(([eventName, handler]) => {
                document.body.removeEventListener(eventName, handler);
            });
        },
        requestClose() {
            this._close();
        },
        retry() {
            this._fetchBody(this._lastUrl);
        },
        followOpenLink(event) {
            event.preventDefault();
            const href = this._openLink.href;
            const isMobile = this._isMobile;
            // The pushed history entry is about to be superseded by a real
            // navigation either way. On mobile it is replaced outright (see
            // below) rather than unwound first, so the close this triggers
            // must leave it alone.
            this._qvSkipHistoryUnwind = true;
            this._close();
            if (isMobile) {
                // assign() would leave the sheet's pushed entry sitting
                // under the destination, so Back from there would first
                // replay this same page before actually leaving it.
                window.location.replace(href);
            } else {
                window.location.assign(href);
            }
        },
        _open(trigger) {
            if (!this._qvDialog.open) {
                this._showDialog();
            }
            this._openLink.href = trigger.href;
            // No focus trap and no scroll lock on desktop, so returning
            // focus to the trigger is the only focus management needed
            // there. The mobile modal sheet gets native focus containment.
            if (!this._isMobile) trigger.focus();
            this._qvTrigger = trigger;
            this._syncExpanded();
        },
        // Opens the dialog in whichever mode _isMobile currently names.
        // showModal() pushes no history entry of its own, so a mobile open
        // adds one by hand; Back then dismisses the sheet instead of
        // navigating the page. A breakpoint flip back to mobile can arrive
        // here with an earlier push still untraversed (the close handler
        // above left _qvHistoryPushed true for exactly that reason), so
        // only push when the sheet does not already own one.
        _showDialog() {
            if (this._isMobile) {
                this._qvDialog.showModal();
                if (!this._qvHistoryPushed) {
                    history.pushState({ flsQuickView: true }, "");
                    this._qvHistoryPushed = true;
                }
            } else {
                this._qvDialog.show();
            }
        },
        _startLoading(trigger, url) {
            const clone = this._skeletonTemplate.content.cloneNode(true);
            const root = clone.firstElementChild;
            if (root) {
                Array.from(trigger.attributes)
                    .filter((attr) => attr.name.startsWith("data-"))
                    .forEach((attr) => root.setAttribute(attr.name, attr.value));
            }
            this._qvBody.replaceChildren(clone);
            this._qvBody.setAttribute("aria-busy", "true");
            // The title comes only from the frame, so it stays blank until
            // one arrives rather than showing the last entity's.
            this._title.textContent = "";
        },
        _afterBodySwap(event) {
            this._qvBody.removeAttribute("aria-busy");
            const frame = this._qvBody.firstElementChild;
            const title = (frame && frame.dataset.quickViewTitle) || "";
            this._title.textContent = title;
            this._entityId = frame ? frame.dataset.entityId : null;
            this._shownUrl = event.detail.pathInfo.requestPath;
            this._stale = false;
            this._status.textContent = "Showing " + title;
            this._registerRefreshEvents(frame ? frame.dataset.refreshEvents : "");
        },
        _handleBodyError(event) {
            if (event.detail.target !== this._qvBody) return;
            this._qvBody.removeAttribute("aria-busy");
            this._qvBody.replaceChildren(this._errorTemplate.content.cloneNode(true));
            this._lastUrl = event.detail.pathInfo.requestPath;
        },
        _syncExpanded() {
            document.querySelectorAll('[aria-controls="quick-view"]').forEach((trigger) => {
                const isShown =
                    this._qvDialog.open && trigger.getAttribute("hx-get") === this._shownUrl;
                trigger.setAttribute("aria-expanded", isShown ? "true" : "false");
            });
        },
        // The events the shown content depends on. A matching event naming
        // the shown entity means its content may be out of date: refetch
        // immediately while open, or mark it stale so the next open
        // refetches instead of reusing what's already on screen.
        _registerRefreshEvents(names) {
            this._refreshHandlers.forEach(([eventName, handler]) => {
                document.body.removeEventListener(eventName, handler);
            });
            this._refreshHandlers = (names || "")
                .split(/\s+/)
                .filter(Boolean)
                .map((eventName) => {
                    const handler = (event) => this._handleRefreshEvent(event);
                    document.body.addEventListener(eventName, handler);
                    return [eventName, handler];
                });
        },
        _handleRefreshEvent(event) {
            const ids = (event.detail && event.detail.ids) || [];
            if (!ids.includes(this._entityId)) return;
            if (this._qvDialog.open) {
                this._fetchBody(this._shownUrl);
            } else {
                this._stale = true;
            }
        },
        _fetchBody(url) {
            htmx.ajax("GET", url, {
                target: "#quick-view-body",
                swap: "innerHTML",
            });
        },
        _close() {
            if (this._qvDialog.open) this._qvDialog.close();
        },
    }));

    // Sidebar menu item component (panel_framework/partials/sidebar_nav.html)
    Alpine.data("sidebarMenuItem", () => ({
        expanded: false,
        init() {
            this.expanded = this.$el.dataset.expanded === "true";
        },
        toggle() {
            this.expanded = !this.expanded;
        },
        close() {
            this.expanded = false;
        },
    }));

    // List-view table auto-refresh (panel_framework/partials/list_refresh.html).
    // Re-fetches the list's table region when a create action's HX-Trigger
    // event fires.
    Alpine.data("listRefresh", () => ({
        _handlers: [],
        init() {
            const url = this.$el.dataset.refreshUrl;
            const target = this.$el.dataset.refreshTarget;
            const events = (this.$el.dataset.refreshEvents || "")
                .split(/\s+/)
                .filter(Boolean);
            events.forEach((eventName) => {
                const handler = () => {
                    htmx.ajax("GET", url, {
                        target: "#" + target,
                        swap: "outerHTML",
                    });
                };
                document.body.addEventListener(eventName, handler);
                this._handlers.push([eventName, handler]);
            });
        },
        destroy() {
            this._handlers.forEach(([eventName, handler]) => {
                document.body.removeEventListener(eventName, handler);
            });
        },
    }));
});

// A tab link lives outside the region it swaps, so the server-rendered
// aria-current on the nav goes stale after a tab switch. Move it to the link
// that made the request. Focus stays where the reader put it.
document.addEventListener("htmx:afterSwap", (event) => {
    if (!event.target.hasAttribute("data-tab-set")) return;
    const link = event.detail.requestConfig && event.detail.requestConfig.elt;
    if (!link || !link.closest("nav")) return;
    link.closest("ul")
        .querySelectorAll("a[aria-current]")
        .forEach((a) => a.removeAttribute("aria-current"));
    link.setAttribute("aria-current", "page");
});

// A saved edit renames the instance it edited. Panels re-fetch themselves on
// their own declared domain events through their own hx-trigger; the page
// heading and the breadcrumb trail's current-page crumb are both outside
// every panel, so they are updated here. The current-instance crumb is the
// only one under #breadcrumbs without a link (see _build_breadcrumbs), so
// it is the sole match for aria-current="page".
document.addEventListener("instanceTitleChanged", (event) => {
    const title = event.detail && event.detail.title;
    if (!title) return;
    const heading = document.getElementById("instance-title");
    if (heading) heading.textContent = title;
    const crumb = document.querySelector('#breadcrumbs [aria-current="page"]');
    if (crumb) crumb.textContent = title;
});
