/**
 * Alpine.js CSP-compatible component registrations for panel_framework.
 *
 * Load this script BEFORE the Alpine CSP script and AFTER the base
 * alpine-components.js script.
 */

document.addEventListener("alpine:init", () => {
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
// panelChanged through their own hx-trigger; the page heading is outside
// every panel, so it is updated here.
document.addEventListener("panelChanged", (event) => {
    const title = event.detail && event.detail.instanceTitle;
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
