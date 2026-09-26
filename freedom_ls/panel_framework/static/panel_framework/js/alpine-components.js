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
// panelChanged through their own hx-trigger; the page heading is outside
// every panel, so it is updated here.
document.addEventListener("panelChanged", (event) => {
    const title = event.detail && event.detail.instanceTitle;
    const heading = document.getElementById("instance-title");
    if (title && heading) heading.textContent = title;
});
