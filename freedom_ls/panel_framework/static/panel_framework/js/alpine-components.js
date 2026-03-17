/**
 * Alpine.js CSP-compatible component registrations for panel_framework.
 *
 * Load this script BEFORE the Alpine CSP script and AFTER the base
 * alpine-components.js script.
 */

document.addEventListener("alpine:init", () => {
    // Tab container component (panel_framework/partials/tab_container.html)
    Alpine.data("tabContainer", () => ({
        activeTab: "",
        loadedTabs: {},
        baseUrl: "",
        defaultTab: "",
        _popstateHandler: null,
        _panelChangedHandler: null,
        init() {
            this.activeTab = this.$el.dataset.activeTab || "";
            this.baseUrl = this.$el.dataset.baseUrl || "";
            this.defaultTab = this.$el.dataset.defaultTab || "";
            this.loadedTabs = { [this.activeTab]: true };

            this._popstateHandler = () => {
                const match = window.location.pathname.match(/__tabs\/([^/]+)/);
                this.switchTab(match ? match[1] : this.defaultTab);
            };
            window.addEventListener("popstate", this._popstateHandler);

            this._panelChangedHandler = (event) => {
                const detail = event.detail || {};
                if (detail.instanceTitle) {
                    const heading = document.getElementById("instance-title");
                    if (heading) heading.textContent = detail.instanceTitle;
                }
                const panel = document.getElementById(
                    "tab-content-" + this.activeTab,
                );
                if (panel) {
                    const url = panel.dataset.tabUrl;
                    if (url) {
                        htmx.ajax("GET", url, {
                            target: panel,
                            swap: "innerHTML",
                        });
                    }
                }
            };
            document.body.addEventListener(
                "panelChanged",
                this._panelChangedHandler,
            );

            this.$watch("activeTab", () => this._updateTabUI());
            this.$nextTick(() => this._updateTabUI());
        },
        destroy() {
            if (this._popstateHandler) {
                window.removeEventListener("popstate", this._popstateHandler);
            }
            if (this._panelChangedHandler) {
                document.body.removeEventListener(
                    "panelChanged",
                    this._panelChangedHandler,
                );
            }
        },
        handleTabClick(event) {
            const button = event.currentTarget;
            const name = button.dataset.tabName;
            if (name) {
                this.switchTab(name);
                const url =
                    name === this.defaultTab
                        ? this.baseUrl
                        : this.baseUrl + "/__tabs/" + name;
                history.pushState({}, "", url);
            }
        },
        switchTab(name) {
            this.activeTab = name;
            if (!this.loadedTabs[name]) {
                this.loadedTabs[name] = true;
                this.$nextTick(() => {
                    const panel = document.getElementById("tab-content-" + name);
                    if (panel) {
                        // The hx-trigger="load-tab" is on a child div inside the panel
                        const htmxEl = panel.querySelector("[hx-trigger]") || panel;
                        htmx.trigger(htmxEl, "load-tab");
                    }
                });
            }
        },
        _updateTabUI() {
            const name = this.activeTab;
            // Show/hide tab panels
            this.$el.querySelectorAll("[data-tab-panel]").forEach((panel) => {
                panel.hidden = panel.dataset.tabPanel !== name;
            });
            // Update tab button styles
            this.$el.querySelectorAll("[data-tab-name]").forEach((btn) => {
                const isActive = btn.dataset.tabName === name;
                btn.classList.toggle("border-b-2", isActive);
                btn.classList.toggle("border-primary", isActive);
                btn.classList.toggle("text-primary", isActive);
                btn.classList.toggle("font-semibold", isActive);
                btn.classList.toggle("text-muted", !isActive);
                btn.classList.toggle("hover:text-foreground", !isActive);
                btn.setAttribute("aria-selected", isActive.toString());
            });
        },
    }));
});
