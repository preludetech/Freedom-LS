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
                focusTriggerOrMain(this._trigger);
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
        _afterBodySwap(event) {
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
// heading is outside every panel, so it is updated here.
document.addEventListener("instanceTitleChanged", (event) => {
    const title = event.detail && event.detail.title;
    const heading = document.getElementById("instance-title");
    if (title && heading) heading.textContent = title;
});
