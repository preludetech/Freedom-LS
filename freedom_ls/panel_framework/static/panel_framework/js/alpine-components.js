/**
 * Alpine.js CSP-compatible component registrations for panel_framework.
 *
 * Load this script BEFORE the Alpine CSP script and AFTER the base
 * alpine-components.js script.
 */

// An unmarked 403 or 404 on an htmx request is a full page: the user has lost
// access to what they are looking at, so the page reloads onto the page a
// fresh visit shows instead of a click that does nothing. This belongs to the
// panel framework's pages alone: a learner page with a half-filled form must
// keep what was typed, so the base script never reloads. Only a real user
// action reloads, so polling and scripted refreshes can never loop.
// #interface-main has its own fallback, and a container that draws its own
// error state (data-htmx-owns-errors) keeps doing so.
//
// A 404 marked data-htmx-swap-error is the action-unavailable dialog. Inside
// #app-modal it swaps in place (a run poll stops polling once it lands).
// Elsewhere (a table region, the quick view) it opens in #app-modal instead
// of replacing the thing that asked, and like the reload it needs a real user
// action: a table that refetched on a domain event stays as it is, rather
// than a dialog opening with nothing to explain it.
document.addEventListener("htmx:beforeSwap", (event) => {
    const status = event.detail.xhr.status;
    if (status !== 403 && status !== 404) return;
    const body = event.detail.xhr.responseText || "";
    const trigger =
        event.detail.requestConfig && event.detail.requestConfig.triggeringEvent;
    const userAction = Boolean(trigger && trigger.isTrusted);
    const target = event.detail.target;
    if (body.includes("data-htmx-swap-error")) {
        if (status === 404 && target && !target.closest("#app-modal")) {
            if (userAction) showUnavailableInModal(event);
            else event.detail.shouldSwap = false;
        }
        return;
    }
    if (
        userAction &&
        target &&
        target.id !== "interface-main" &&
        !target.closest("[data-htmx-owns-errors]")
    ) {
        event.detail.shouldSwap = false;
        window.location.reload();
    }
});

function showUnavailableInModal(event) {
    const target = event.detail.target;
    const modal = document.getElementById("app-modal");
    const modalBody = document.getElementById("app-modal-body");
    if (!modal || !modalBody) return;
    // appModal records its trigger only for requests aimed at its body, so
    // the element to return focus to on close is handed over here: the
    // control that asked (a sort link, a filter), or the row link that opened
    // the quick view.
    const modalData = Alpine.$data(modal);
    modalData._trigger = event.detail.elt;
    if (target.id === "quick-view-body") {
        // The drawer holds only its skeleton here: close it, and mark it stale
        // so the next open refetches instead of reusing the skeleton.
        const drawer = document.getElementById("quick-view");
        if (drawer) {
            const drawerData = Alpine.$data(drawer);
            modalData._trigger = drawerData._qvTrigger;
            drawerData._stale = true;
            drawer.close();
        }
    }
    event.detail.target = modalBody;
    event.detail.swapOverride = "innerHTML";
}

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

// Writes the dirty form's own discard wording into a host's discard prompt,
// as text and never HTML, and leaves the prompt's defaults when the form
// names none. Shared by appModal and quickView.
function fillDiscardPrompt(prompt, form) {
    const title = prompt.querySelector("[data-discard-title]");
    const body = prompt.querySelector("[data-discard-body]");
    if (title && form && form.dataset.discardTitle) {
        title.textContent = form.dataset.discardTitle;
    }
    if (body && form && form.dataset.discardBody) {
        body.textContent = form.dataset.discardBody;
    }
}

// Tracks whether the first form inside a container differs from what it held
// at the last snapshot(), so a field edited and then changed back reads clean.
// Both FormData objects come from the same form element, so their entries()
// order is stable and the joined pairs are safe to compare as strings.
// `ignore` is a selector for fields that never count as an edit (hidden
// inputs a script rewrites on its own). snapshot() takes the names of fields
// to record as empty: used when the server hands back text the user has not
// sent, so that text still reads as an edit.
function dirtyTracker(container, ignore = "") {
    let baseline = null;

    function read(form) {
        const data = new FormData(form);
        if (ignore) {
            form.querySelectorAll(ignore).forEach((field) => data.delete(field.name));
        }
        return data;
    }

    function serialise(formData) {
        if (!formData) return "";
        return Array.from(formData.entries())
            .map(([name, value]) => `${name}=${value}`)
            .join("&");
    }

    return {
        snapshot(blankFields = []) {
            const form = container.querySelector("form");
            baseline = form ? read(form) : null;
            if (baseline) blankFields.forEach((name) => baseline.set(name, ""));
        },
        isDirty() {
            const form = container.querySelector("form");
            return form !== null && serialise(read(form)) !== serialise(baseline);
        },
    };
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
        dirty: false,
        init() {
            this._dialog = this.$el;
            this._body = document.getElementById("app-modal-body");
            this._tracker = dirtyTracker(this._body);

            // hx-disabled-elt blurs the trigger before showModal() runs, so
            // native focus return cannot be relied on — the trigger is
            // recorded here instead, while it is still the active element.
            // The previous fragment is dropped here too, not on close: below
            // sm the sheet is still sliding out when close fires, and would
            // go down the screen empty.
            trackListener(this._handlers, document, "htmx:beforeRequest", (event) => {
                if (event.detail.target === this._body && !this._dialog.open) {
                    this._body.innerHTML = "";
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
                this._hideDiscardPrompt();
                this._tracker.snapshot();
                this.dirty = false;
                // A result announced in this open is not re-read on the next.
                // A host that shadows modal_host.html may lack the region.
                const status = document.getElementById("app-modal-status");
                if (status) status.textContent = "";
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

            // A click on the ::backdrop targets the dialog element itself, but
            // so does one on the dialog's own padding: only a click outside
            // the dialog's box is a backdrop click. It is only meaningful when
            // the fragment holds no form: a destructive confirmation or
            // read-only content, never something with unsaved input.
            trackListener(this._handlers, this._dialog, "click", (event) => {
                if (event.target !== this._dialog || this._body.querySelector("form")) {
                    return;
                }
                const box = this._dialog.getBoundingClientRect();
                const inside =
                    event.clientX >= box.left &&
                    event.clientX <= box.right &&
                    event.clientY >= box.top &&
                    event.clientY <= box.bottom;
                if (!inside) this._dialog.close();
            });

            // htmx caches the outgoing page's DOM before pushing the new URL,
            // so an open dialog would otherwise be part of that snapshot and
            // reopen on Back.
            trackListener(this._handlers, document, "htmx:beforeHistorySave", () => {
                if (this._dialog.open) this._dialog.close();
            });

            // The bottom fade (modal_host.html) shows while content lies
            // below the fold: re-measured on scroll, when the body changes
            // size (a fragment landing, an image loading, a section
            // expanding) and when the dialog opens.
            trackListener(this._handlers, this._dialog, "scroll", () => this._syncMoreBelow());
            trackListener(this._handlers, this._dialog, "toggle", () => this._syncMoreBelow());
            this._resizeObserver = new ResizeObserver(() => this._syncMoreBelow());
            this._resizeObserver.observe(this._body);
        },
        destroy() {
            this._handlers.forEach(([target, type, handler, options]) => {
                target.removeEventListener(type, handler, options);
            });
            if (this._resizeObserver) this._resizeObserver.disconnect();
        },
        _syncMoreBelow() {
            const dialog = this._dialog;
            const more = dialog.open && dialog.scrollHeight - dialog.scrollTop - dialog.clientHeight > 8;
            dialog.dataset.moreBelow = more ? "true" : "false";
        },
        requestClose() {
            if (typeof this._dialog.requestClose === "function") {
                this._dialog.requestClose();
            } else {
                this._dialog.close();
            }
        },
        // A form's own Cancel button is a deliberate choice to drop the
        // input, so it closes without the dirty-form guard that the close
        // control and Esc go through.
        cancel() {
            this._dialog.close();
        },
        // Brings the form back in place of the discard prompt. Called from
        // the prompt's "Keep editing" button.
        keepEditing() {
            this._hideDiscardPrompt();
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
            // htmx wires a swapped-in fragment's hx-* attributes in its settle
            // phase, a beat after afterSwap. Opening the dialog first would
            // show controls that ignore the first interaction (a select whose
            // hx-get fires on change), so wire them now; process is idempotent.
            htmx.process(this._body);
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
            this._tracker.snapshot();
            this.dirty = false;
        },
        _checkDirty() {
            this.dirty = this._tracker.isDirty();
        },
        // The prompt takes the fragment's place, and the dialog's
        // accessible name moves to the prompt's heading with it.
        _showDiscardPrompt() {
            const prompt = this._dialog.querySelector("[data-discard-prompt]");
            if (!prompt) return;
            fillDiscardPrompt(prompt, this._body.querySelector("form"));
            this._body.hidden = true;
            prompt.hidden = false;
            this._dialog.setAttribute("aria-labelledby", "app-modal-discard-title");
            const keepEditingButton = prompt.querySelector("[autofocus]");
            if (keepEditingButton) keepEditingButton.focus();
        },
        _hideDiscardPrompt() {
            const prompt = this._dialog.querySelector("[data-discard-prompt]");
            if (prompt) prompt.hidden = true;
            this._body.hidden = false;
            this._dialog.setAttribute("aria-labelledby", "app-modal-title");
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
        _qvTrigger: null,
        _shownUrl: null,
        _stale: false,
        _qvDirty: false,
        _pendingAction: null,
        _entityId: null,
        _refreshHandlers: [],
        _lastUrl: null,
        _qvHandlers: [],
        init() {
            this._qvDialog = this.$el;
            this._qvBody = document.getElementById("quick-view-body");
            this._title = document.getElementById("quick-view-title");
            this._subtitle = document.getElementById("quick-view-subtitle");
            this._openLink = document.getElementById("quick-view-open");
            this._status = document.getElementById("quick-view-status");
            this._skeletonTemplate = this._qvDialog.querySelector(
                "[data-quick-view-skeleton]",
            );
            this._errorTemplate = this._qvDialog.querySelector("[data-quick-view-error]");
            this._discardPrompt = this._qvDialog.querySelector(
                "[data-discard-prompt]",
            );
            // Hidden inputs (the composer's draft flag and send key) are
            // rewritten by scripts and by every send; only fields a person
            // edits count towards an unsent draft.
            this._qvTracker = dirtyTracker(this._qvBody, "input[type=hidden]");

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
                // A history restore (Back, with historyCacheSize 0) replaces
                // the whole <body>, recreating this component on a fresh
                // dialog rather than leaving the old one in place the way a
                // plain #main-content swap does. Alpine's own teardown of the
                // outgoing instance can lag behind a click on the newly
                // restored trigger, so this stale instance — still carrying
                // the _shownUrl of whatever it last showed — would otherwise
                // intercept the event and call show() on its own
                // detached dialog instead of leaving it to the fresh
                // instance. Bailing out here once the dialog is no longer in
                // the document makes that race harmless.
                if (!this._qvDialog.isConnected) return;
                const trigger = event.detail.elt;
                if (!trigger || !trigger.matches('[aria-controls="quick-view"]')) return;
                const url = event.detail.path;
                if (url === this._shownUrl && this._qvDialog.open) {
                    event.preventDefault();
                    this._requestClose();
                    return;
                }
                if (url === this._shownUrl && !this._stale) {
                    event.preventDefault();
                    this._open(trigger);
                    return;
                }
                if (this._qvDialog.open && this._qvDirty) {
                    // Hold the request until the prompt is answered.
                    event.preventDefault();
                    this._showDiscardPrompt(() => {
                        this._open(trigger);
                        this._startLoading(trigger, url);
                        event.detail.issueRequest(true);
                    });
                    return;
                }
                this._open(trigger);
                this._startLoading(trigger, url);
            });

            // A fragment is dirty when its form no longer matches the snapshot
            // taken as it swapped in.
            trackListener(this._qvHandlers, this._qvBody, "input", () => this._checkDirty());
            trackListener(this._qvHandlers, this._qvBody, "change", () => this._checkDirty());

            trackListener(this._qvHandlers, document, "htmx:afterSwap", (event) => {
                if (event.detail.target === this._qvBody) {
                    this._afterBodySwap(event);
                } else if (this._isBoxSwap(event.detail.target)) {
                    // A send replaces the form inside the body without
                    // reloading the drawer: what is on screen is the new
                    // baseline, except text the server returned unsent.
                    this._snapshotBody(event.detail.xhr.status === 422 ? ["body"] : []);
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

            // Single point every dismiss route (Esc, requestClose()) funnels
            // through.
            trackListener(this._qvHandlers, this._qvDialog, "close", () => {
                // A dialog reopened in the other mode (see the breakpoint
                // listener below) is still on screen.
                if (this._qvDialog.open) return;
                this._hideDiscardPrompt();
                this._qvTracker.snapshot();
                this._qvDirty = false;
                this._syncExpanded();
                focusTriggerOrMain(this._qvTrigger);
            });

            // A modal dialog closes on Escape by itself; cancel routes that
            // through the same unsaved-draft guard as every other dismiss.
            trackListener(this._qvHandlers, this._qvDialog, "cancel", (event) => {
                event.preventDefault();
                this._requestClose();
            });

            // show() gives a dialog no Esc-to-close of its own, so this adds
            // it, and steps aside when some other dialog (e.g. #app-modal)
            // is the one currently in the top layer, or when some other
            // layer above the drawer (e.g. an open dropdown menu) already
            // consumed this Escape via preventDefault(). That layer's own
            // handler has to run first for this check to see it: this
            // listener stays on the bubble phase, and a capture-phase
            // Escape handler (dropdown-menu.html's onEscape) always
            // finishes before any bubble-phase listener runs, whatever
            // order the two components happened to initialise in.
            trackListener(this._qvHandlers, document, "keydown", (event) => {
                if (event.key !== "Escape") return;
                if (!this._qvDialog.open) return;
                if (document.querySelector("dialog[open]:modal")) return;
                if (event.defaultPrevented) return;
                this._requestClose();
            });

            // htmx caches the outgoing page's DOM before pushing the new
            // URL, so an open drawer would otherwise be part of that
            // snapshot and reopen on Back.
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
            this._requestClose();
        },
        // Brings the form back in place of the discard prompt.
        keepEditing() {
            this._hideDiscardPrompt();
            const field = this._qvBody.querySelector("textarea, input:not([type=hidden]), select");
            if (field) field.focus();
        },
        // The prompt has already confirmed the loss of the input, so the
        // action it held runs without the guard.
        discard() {
            const action = this._pendingAction;
            this._hideDiscardPrompt();
            this._qvDirty = false;
            if (action) action();
        },
        retry() {
            this._fetchBody(this._lastUrl);
        },
        // Never modal, at any width: the page behind the drawer stays
        // usable, so the next row can be previewed with a tap on it. A
        // modal is for a decision; a quick view is a look.
        _showDialog() {
            this._qvDialog.show();
        },
        _open(trigger) {
            if (!this._qvDialog.open) this._showDialog();
            this._openLink.href = trigger.href;
            // Focus moves to the heading so a keyboard reader lands in the
            // drawer; closing returns it to the trigger.
            this._title.focus();
            this._qvTrigger = trigger;
            this._syncExpanded();
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
            this._subtitle.textContent = "";
            // The drawer now belongs to this url, loaded or not, so a click on
            // any other trigger loads that one rather than reusing what was
            // shown before this load started.
            this._shownUrl = url;
        },
        _afterBodySwap(event) {
            this._qvBody.removeAttribute("aria-busy");
            const frame = this._qvBody.firstElementChild;
            const title = (frame && frame.dataset.quickViewTitle) || "";
            this._title.textContent = title;
            this._subtitle.textContent = (frame && frame.dataset.quickViewSubtitle) || "";
            this._snapshotBody();
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
            // The error block is not worth reusing: the next open refetches.
            this._stale = true;
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
            // A refetch would replace a draft the reader has not sent.
            if (this._qvDialog.open && !this._qvDirty) {
                this._fetchBody(this._shownUrl);
            } else {
                this._stale = true;
            }
        },
        _isBoxSwap(target) {
            return (
                !!target && (target.id === "quick-view-message-box" || this._qvBody.contains(target))
            );
        },
        _snapshotBody(blankFields = []) {
            this._qvTracker.snapshot(blankFields);
            this._qvDirty = false;
            if (blankFields.length) this._checkDirty();
        },
        _checkDirty() {
            this._qvDirty = this._qvTracker.isDirty();
        },
        // Esc, the close control and a second click on the shown row all
        // ask first when the drawer holds an unsent draft.
        _requestClose() {
            if (this._qvDialog.open && this._qvDirty) {
                // The drawer keeps its content while closed, so a discarded
                // draft would reappear on reopen unless it is refetched.
                this._showDiscardPrompt(() => {
                    this._stale = true;
                    this._close();
                });
                return;
            }
            this._close();
        },
        // The prompt takes the body's place; pendingAction runs on Discard.
        _showDiscardPrompt(pendingAction) {
            if (!this._discardPrompt) {
                pendingAction();
                return;
            }
            this._pendingAction = pendingAction;
            fillDiscardPrompt(this._discardPrompt, this._qvBody.querySelector("form"));
            this._qvBody.hidden = true;
            this._discardPrompt.hidden = false;
            const keepButton = this._discardPrompt.querySelector("[autofocus]");
            if (keepButton) keepButton.focus();
        },
        _hideDiscardPrompt() {
            this._pendingAction = null;
            if (this._discardPrompt) this._discardPrompt.hidden = true;
            this._qvBody.hidden = false;
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

    // Row selection for a table's bulk-action bar (cotton/data-table.html).
    // Lives on the table region so one scope covers the toolbar, the bar and
    // the table. The toolbar's search form is outside the bulk form, which is
    // why the handlers find the bulk form from the hidden mode input rather
    // than from the region. There is no persisted state: every region swap
    // re-renders the region from scratch, which is how a sort, search or
    // filter change clears the selection.
    Alpine.data("tableSelection", () => ({
        count: 0,
        // "keys" submits the ticked rows; "all_matching" submits every row
        // the table's filters match, minus the keys in `excluded`.
        mode: "keys",
        excluded: [],
        total: 0,
        page: 0,
        allChecked: false,
        regionId: "",

        init() {
            const bar = this.$el.querySelector("[data-total-count]");
            this.total = Number(bar.dataset.totalCount);
            this.page = Number(bar.dataset.pageCount);
            this.regionId = this.$el.id;
            // The stylesheet hides a pending bar; from here on x-show decides.
            bar.removeAttribute("data-selection-bar-pending");
        },

        // The bulk form, which the search form in the toolbar must never be
        // mistaken for: the hidden mode input belongs to the bulk form alone.
        _form() {
            return this.$refs.modeInput.form;
        },

        get hasSelection() {
            return this.count > 0;
        },

        get barVisible() {
            return this.hasSelection || this.running;
        },

        // The toolbar gives its row to the bar at every width. The bar's
        // display is bound the same way, so both change in the same frame:
        // x-show would apply a frame later and leave the table a row lower or
        // higher. Important, so it beats the toolbar's md:flex.
        toolbarClass() {
            return this.barVisible ? "hidden!" : "";
        },

        barStyle() {
            return { display: this.barVisible ? "" : "none" };
        },

        get countSentence() {
            if (this.running) return this.runLabel + " is running…";
            if (this.hasSelection) return this.count + " selected";
            return "";
        },

        // A background run started from this table, kept in the bulkRuns
        // store because every region swap rebuilds this component.
        get run() {
            return Alpine.store("bulkRuns").runs[this.regionId] || null;
        },

        get running() {
            return this.run !== null;
        },

        get runLabel() {
            return this.running ? this.run.label : "";
        },

        // The action buttons give way to the status line while a run is going,
        // so the bar does not grow a second row of disabled buttons.
        get actionsVisible() {
            return this.hasSelection && !this.running;
        },

        // Below md every row has two checkboxes — one in the desktop <table>,
        // one on its card — with only one ever visible at a time. Counting
        // and "select all" both need just the reachable set, or checking
        // every visible row would never look "all checked" against the
        // hidden half. offsetParent is null exactly for a display:none
        // ancestor, which is how both the table and the card list hide.
        _visibleRowBoxes(form) {
            return Array.from(form.querySelectorAll('input[name="keys"]')).filter(
                (box) => box.offsetParent !== null,
            );
        },

        // Recount the visible row boxes and sync every page checkbox:
        // unchecked when none are ticked, indeterminate when some are,
        // checked when all are.
        update() {
            const form = this._form();
            const rowBoxes = this._visibleRowBoxes(form);
            const checkedBoxes = rowBoxes.filter((box) => box.checked);
            const allChecked =
                rowBoxes.length > 0 && checkedBoxes.length === rowBoxes.length;
            this.allChecked = allChecked;
            if (this.mode === "all_matching") {
                // Only this page's rows can be unticked: a swap to another
                // page rebuilds the component and clears the selection.
                this.excluded = rowBoxes
                    .filter((box) => !box.checked)
                    .map((box) => box.value);
                this._syncExcludedInputs();
                this.count = this.total - this.excluded.length;
            } else {
                this.count = checkedBoxes.length;
            }
            form.querySelectorAll("[data-select-all]").forEach((box) => {
                box.checked = allChecked;
                box.indeterminate = checkedBoxes.length > 0 && !allChecked;
            });
        },

        _syncExcludedInputs() {
            const inputs = this.excluded.map((key) => {
                const input = document.createElement("input");
                input.type = "hidden";
                input.name = "excluded";
                input.value = key;
                return input;
            });
            this.$refs.excluded.replaceChildren(...inputs);
        },

        _setMode(mode) {
            this.mode = mode;
            this.$refs.modeInput.value = mode;
        },

        selectAllMatching() {
            this._setMode("all_matching");
            this.excluded = [];
            this._syncExcludedInputs();
            this.count = this.total;
        },

        // A control inside the bar that empties the selection takes the bar
        // away with it, so focus is moved to the page checkbox that is
        // actually on screen: the header's from md up, the card list's below.
        _returnFocus(event) {
            if (!event.target.closest("[data-total-count]")) return;
            const box = Array.from(
                this.$root.querySelectorAll("[data-select-all]"),
            ).find(
                (candidate) =>
                    candidate.offsetParent !== null &&
                    !candidate.closest("[data-total-count]"),
            );
            if (box) box.focus();
        },

        clearSelection(event) {
            this._setMode("keys");
            this.excluded = [];
            this._syncExcludedInputs();
            const form = this._form();
            this._visibleRowBoxes(form).forEach((box) => {
                box.checked = false;
            });
            this.count = 0;
            this.allChecked = false;
            form.querySelectorAll("[data-select-all]").forEach((box) => {
                box.checked = false;
                box.indeterminate = false;
            });
            this._returnFocus(event);
        },

        toggleAll(event) {
            const checked = event.target.checked;
            this._visibleRowBoxes(this._form()).forEach((box) => {
                box.checked = checked;
            });
            this.update();
            if (!this.hasSelection) this._returnFocus(event);
        },

        get allMatchingMode() {
            return this.mode === "all_matching";
        },

        // Every row the table's filters match is selected: in all_matching
        // mode nothing has been unticked, and in page mode the page holds
        // every match and every row on it is ticked.
        get allMatchingSelected() {
            if (!this.hasSelection) return false;
            if (this.allMatchingMode) return this.excluded.length === 0;
            return this.allChecked && this.total <= this.page;
        },

        get selectAllLabel() {
            return this.allMatchingSelected
                ? "Deselect all"
                : "Select all " + this.total;
        },

        // One link for both directions. Selecting ticks the visible rows
        // first so the page checkboxes agree with the count; only a table
        // with more matches than this page switches to all_matching mode.
        activateSelectAll(event) {
            if (this.allMatchingSelected) {
                this.clearSelection(event);
                return;
            }
            this._visibleRowBoxes(this._form()).forEach((box) => {
                box.checked = true;
            });
            this.update();
            if (this.total > this.page) this.selectAllMatching();
        },
    }));

    // Background bulk runs, keyed by the id of the table region they were
    // started from. A confirmed run too large for one request answers with
    // a bulkRunStarted event; the run's status URL is then polled until it
    // returns the result modal, whose HX-Trigger refreshes the table. A 204
    // means still running. Leaving the table drops the run here: the
    // requester gets a notification instead.
    Alpine.store("bulkRuns", {
        runs: {},
        _timers: {},

        init() {
            document.body.addEventListener("bulkRunStarted", (event) => {
                this.start(event.detail);
            });
            document.addEventListener("htmx:afterRequest", (event) => {
                const path = event.detail.pathInfo && event.detail.pathInfo.requestPath;
                const region = Object.keys(this.runs).find(
                    (key) => this.runs[key].status_url === path,
                );
                if (region && event.detail.xhr.status !== 204) this.finish(region);
            });
        },

        start(detail) {
            this.finish(detail.region);
            this.runs[detail.region] = detail;
            this._timers[detail.region] = setInterval(() => this._poll(detail.region), 2000);
        },

        finish(region) {
            clearInterval(this._timers[region]);
            delete this._timers[region];
            delete this.runs[region];
        },

        _poll(region) {
            const anchor = document.querySelector(`#${region} [data-table-anchor]`);
            if (!anchor) {
                this.finish(region);
                return;
            }
            // Never replace a modal the reader has open, and don't poll a
            // hidden tab; the next tick tries again.
            if (document.hidden || document.getElementById("app-modal").open) return;
            htmx.ajax("GET", this.runs[region].status_url, {
                source: anchor,
                target: "#app-modal-body",
                swap: "innerHTML",
            });
        },
    });

    // Re-requests a region when a named event reaches the body
    // (panel_framework/partials/list_refresh.html and the instance header).
    // data-refresh-events: space-separated event names. data-url: the
    // address to request; the address bar's query string is appended, since
    // it holds every table's live state, so a list stays on the reader's
    // page, sort, search and filters. Without data-url the request goes to
    // the address bar's own path and query, so an instance page keeps its
    // active tab. data-target and data-select are selectors, data-swap an
    // htmx swap style (outerHTML by default). The host sits inside or beside
    // the region it refreshes.
    Alpine.data("eventRefresh", () => ({
        _handlers: [],
        init() {
            const events = (this.$el.dataset.refreshEvents || "")
                .split(/\s+/)
                .filter(Boolean);
            events.forEach((eventName) => {
                const handler = () => this.refresh();
                document.body.addEventListener(eventName, handler);
                this._handlers.push([eventName, handler]);
            });
        },
        destroy() {
            this._handlers.forEach(([eventName, handler]) => {
                document.body.removeEventListener(eventName, handler);
            });
            this._handlers = [];
        },
        refresh() {
            const { url, target, select, swap } = this.$el.dataset;
            const requestUrl = url
                ? url + window.location.search
                : window.location.pathname + window.location.search;
            const options = { target, swap: swap || "outerHTML" };
            if (select) options.select = select;
            htmx.ajax("GET", requestUrl, options);
        },
    }));

    // A form whose submit button is disabled for its request loses keyboard
    // focus to <body>, and the event the request fires may replace the
    // panel the form sits in. After the request, focus moves to the element
    // whose id data-refocus-id names, found in the document as it is then.
    // The CSP build of Alpine runs no inline expression, so the handler is a
    // method: x-on:htmx:after-request="refocus".
    Alpine.data("refocusAfterRequest", () => ({
        refocus() {
            const id = this.$el.dataset.refocusId;
            setTimeout(() => document.getElementById(id)?.focus());
        },
    }));

    // Tab strip (panel_framework/panels/_tab_nav.html). The strip scrolls
    // sideways on a narrow screen and opens at its left end, so a page that
    // loads on one of the last tabs would hide the tab it is on.
    Alpine.data("tabStrip", () => ({
        init() {
            this.$nextTick(() => showActiveTab(this.$el));
        },
    }));

    // Row detail toggle (cotton/data-table.html). x-data sits on the <table>
    // and on the card list below md; each toggle button names its detail (a
    // <tr> in the table, a <div> in a card) through aria-controls, so rows
    // open independently and the server renders every row closed. The detail
    // is switched through `hidden`, which cannot animate, so there is no
    // x-transition: only the chevron moves, through CSS keyed on aria-expanded.
    // Focus stays on the button. An htmx swap of the region replaces the
    // <table>, so a fresh instance starts with every row closed.
    Alpine.data("rowDetail", () => ({
        toggle(event) {
            const button = event.currentTarget;
            const detail = document.getElementById(button.getAttribute("aria-controls"));
            if (!detail) return;
            const opening = detail.hidden;
            detail.hidden = !opening;
            button.setAttribute("aria-expanded", String(opening));
        },
    }));
});

// Scroll a tab strip sideways just far enough to show its active tab whole.
// The strip's own scroll offset is set, so the page itself never moves.
function showActiveTab(strip) {
    const active = strip.querySelector('a[aria-current="page"]');
    if (!active) return;
    const stripBox = strip.getBoundingClientRect();
    const tabBox = active.getBoundingClientRect();
    if (tabBox.left < stripBox.left) {
        strip.scrollLeft -= stripBox.left - tabBox.left;
    } else if (tabBox.right > stripBox.right) {
        strip.scrollLeft += tabBox.right - stripBox.right;
    }
}

// A tab link lives outside the region it swaps, so the server-rendered
// aria-current on the nav goes stale after a tab switch. Move it to the link
// that made the request, and bring it into view when it was only part
// showing. Focus stays where the reader put it.
document.addEventListener("htmx:afterSwap", (event) => {
    if (!event.target.hasAttribute("data-tab-set")) return;
    const link = event.detail.requestConfig && event.detail.requestConfig.elt;
    if (!link || !link.closest("nav")) return;
    link.closest("ul")
        .querySelectorAll("a[aria-current]")
        .forEach((a) => a.removeAttribute("aria-current"));
    link.setAttribute("aria-current", "page");
    showActiveTab(link.closest("ul"));
});

// A saved edit renames the instance it edited. Panels re-fetch themselves on
// their own declared domain events through their own hx-trigger; the page
// heading is outside every panel, so it is updated here. The browser tab's
// title opens with the same name (the rest of it names the scope and the
// site), so only that leading segment is swapped: the heading's text when the
// title starts with it, otherwise whatever precedes the first " — ".
document.addEventListener("instanceTitleChanged", (event) => {
    const title = event.detail && event.detail.title;
    if (!title) return;
    const heading = document.getElementById("instance-title");
    if (!heading) return;
    const previous = heading.textContent;
    heading.textContent = title;
    if (previous && document.title.startsWith(previous)) {
        document.title = title + document.title.slice(previous.length);
        return;
    }
    const separator = document.title.indexOf(" — ");
    if (separator !== -1) {
        document.title = title + document.title.slice(separator);
    }
});

// A table region swap replaces the whole region element (outerHTML), so the
// element in event.detail.target is the one about to be removed. Look the
// new element back up by id and focus its anchor, so a sort, filter or page
// click moves focus onto the table instead of leaving it on a removed link.
// A swap started from outside the region, such as a list refresh after a
// create, removed nothing the reader was on, so focus stays where it is
// (for example in a still-open create modal).
// A search swap is left alone: the search input survives the swap
// (hx-preserve) and keeps focus, so a reader who pauses can keep typing.
document.addEventListener("htmx:afterSettle", (event) => {
    const target = event.detail.target;
    if (!target || !target.hasAttribute("data-table-region")) return;
    const source = event.detail.requestConfig && event.detail.requestConfig.elt;
    if (!source || !target.contains(source)) return;
    if (source.matches("form[id$='-search']")) return;
    const region = document.getElementById(target.id);
    const anchor = region && region.querySelector("[data-table-anchor]");
    if (anchor) anchor.focus();
});

// A confirmed row action closes the dialog, which refocuses its trigger; the
// panel's own refresh then swaps that trigger out (a removed row, a card that
// re-renders its buttons) and the browser drops focus to <body>. Whether focus
// sat inside the swap target is noted on that request's own config, because
// one confirm can refresh several regions at once and a shared flag would be
// overwritten by whichever swap ran next. The check runs in afterSwap, in the
// same task as the swap, before any other response can move focus again. The
// new region's table anchor, else its first heading (or its panel card's), else the page content
// takes focus, so it is never lost. A swap of #main-content itself is a page
// navigation, and focus goes to #main-content as on any other navigation.
document.addEventListener("htmx:beforeSwap", (event) => {
    const { target, requestConfig } = event.detail;
    const active = document.activeElement;
    if (!requestConfig) return;
    const trigger = requestConfig.triggeringEvent;
    // A form that disables its submit button while posting (hx-disabled-elt)
    // has already lost focus to <body> by now, so a reader's own submit from
    // inside the target counts as focus having been there.
    const submittedFromTarget = Boolean(
        target &&
            trigger &&
            trigger.isTrusted &&
            trigger.type === "submit" &&
            target.contains(requestConfig.elt),
    );
    requestConfig.focusWasInTarget =
        submittedFromTarget ||
        Boolean(target && active && active !== document.body && target.contains(active));
    // The focused element's id, so the same field in the re-rendered
    // region (a name field saved in place) gets focus back.
    requestConfig.focusedId =
        active && active !== document.body && target && target.contains(active) ? active.id : "";
});
document.addEventListener("htmx:afterSwap", (event) => {
    const { target, requestConfig } = event.detail;
    if (!requestConfig || !requestConfig.focusWasInTarget || !target || !target.id) return;
    const active = document.activeElement;
    if (active && active !== document.body && active.isConnected) return;
    const region = document.getElementById(target.id);
    if (!region) return;
    if (region.id === "main-content") {
        region.focus();
        return;
    }
    const sameField = requestConfig.focusedId
        ? region.querySelector("#" + CSS.escape(requestConfig.focusedId))
        : null;
    if (sameField) {
        sameField.focus();
        return;
    }
    let fallback = region.querySelector("[data-table-anchor]");
    if (!fallback) {
        const headings = "h1, h2, h3, h4, h5, h6";
        // A region inside a panel card has no heading of its own: the
        // card's heading names it.
        fallback =
            region.querySelector(headings) ||
            (region.closest("[data-panel]") || region).querySelector(headings);
        if (fallback) fallback.setAttribute("tabindex", "-1");
    }
    (fallback || document.getElementById("main-content")).focus();
});

// A focused search input survives its table region's swap (hx-preserve), but
// once htmx has moved it into the new region Chromium still reports it as
// focused while dropping its caret, so further typing goes nowhere. Refocus
// it and put the caret back in htmx:afterSwap, which runs in the same task as
// the swap, so no keystroke lands in between.
let focusedSearch = null;
document.addEventListener("htmx:beforeSwap", (event) => {
    const active = document.activeElement;
    focusedSearch =
        active &&
        active.matches("input[type='search'][hx-preserve]") &&
        event.detail.target.contains(active)
            ? { input: active, start: active.selectionStart, end: active.selectionEnd }
            : null;
});
document.addEventListener("htmx:afterSwap", () => {
    if (!focusedSearch) return;
    const { input, start, end } = focusedSearch;
    focusedSearch = null;
    if (!input.isConnected) return;
    input.blur();
    input.focus();
    input.setSelectionRange(start, end);
});

// The kept search input (hx-preserve) outlives the value the server rendered
// for it, so a search the server has dropped, such as after the empty state's
// "Clear filters", would stay on screen and re-apply on the next keystroke.
// When the swap was not started by the search form itself, copy the incoming
// input's value onto the kept element. While the user is typing, the form's
// own value stands: the response may lag behind what they have typed since.
document.addEventListener("htmx:beforeSwap", (event) => {
    const target = event.detail.target;
    if (!event.detail.shouldSwap || !target || !target.hasAttribute("data-table-region")) {
        return;
    }
    const source = event.detail.requestConfig && event.detail.requestConfig.elt;
    if (source && source.matches("form[id$='-search']")) return;
    const kept = target.querySelector("input[type='search'][hx-preserve]");
    if (!kept) return;
    const incoming = new DOMParser()
        .parseFromString(event.detail.serverResponse, "text/html")
        .getElementById(kept.id);
    if (incoming) kept.value = incoming.getAttribute("value") || "";
});
