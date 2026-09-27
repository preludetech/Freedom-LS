/**
 * Alpine.js CSP-compatible component registrations for panel_framework.
 *
 * Load this script BEFORE the Alpine CSP script and AFTER the base
 * alpine-components.js script.
 */

// Adds a listener and records it alongside its target and type, so a
// component's destroy() can remove every listener it registered without
// hand-listing them a second time. Shared by appModal and quickView.
function trackListener(handlers, target, type, handler) {
    target.addEventListener(type, handler);
    handlers.push([target, type, handler]);
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

            trackListener(this._handlers, document, "htmx:afterSwap", (event) => {
                if (event.detail.target === this._body) {
                    this._afterBodySwap(event);
                } else if (event.detail.target.id === "main-content") {
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
            this._handlers.forEach(([target, type, handler]) => {
                target.removeEventListener(type, handler);
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

    // Row selection for a table's bulk-action bar (cotton/data-table.html).
    // Lives on the wrapping <form>, so every row and header checkbox reaches
    // it, including the mobile "select all" control and every card checkbox,
    // which render inside the same form. There is no persisted state: every
    // region swap re-renders the form from scratch, which is how a sort,
    // search or filter change clears the selection.
    //
    // Both handlers find the form from the triggering event's target rather
    // than `this.$el`: a shared Alpine.data() method's `$el` is the element
    // the firing x-on directive is declared on, not the component's x-data
    // root, so `this.$el` inside update() would be the checkbox itself.
    Alpine.data("tableSelection", () => ({
        count: 0,

        get hasSelection() {
            return this.count > 0;
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

        // Recount checked rows and sync every header "select all" checkbox
        // to match: unchecked when none are selected, indeterminate when
        // some are, checked when every row on the page is.
        update(event) {
            const form = event.target.closest("form");
            const rowBoxes = this._visibleRowBoxes(form);
            const checkedBoxes = rowBoxes.filter((box) => box.checked);
            this.count = checkedBoxes.length;
            const allChecked =
                rowBoxes.length > 0 && checkedBoxes.length === rowBoxes.length;
            form.querySelectorAll("[data-select-all]").forEach((box) => {
                box.checked = allChecked;
                box.indeterminate = this.count > 0 && !allChecked;
            });
        },

        toggleAll(event) {
            const form = event.target.closest("form");
            const checked = event.target.checked;
            this._visibleRowBoxes(form).forEach((box) => {
                box.checked = checked;
            });
            this.update(event);
        },
    }));

    // List-view table auto-refresh (panel_framework/partials/list_refresh.html).
    // Re-fetches the list's table region when a create action's HX-Trigger
    // event fires. The request carries the address bar's query, which holds
    // every table's live state, so the list stays on the reader's page,
    // sort, search and filters.
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
                    htmx.ajax("GET", url + window.location.search, {
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
// heading is outside every panel, so it is updated here.
document.addEventListener("instanceTitleChanged", (event) => {
    const title = event.detail && event.detail.title;
    const heading = document.getElementById("instance-title");
    if (title && heading) heading.textContent = title;
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
