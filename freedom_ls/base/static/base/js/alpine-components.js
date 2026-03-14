/**
 * Alpine.js CSP-compatible component registrations.
 *
 * The @alpinejs/csp build does not support inline JS expressions.
 * All Alpine components must be registered via Alpine.data().
 * Load this script BEFORE the Alpine CSP script.
 */

// Allow HTMX to swap content on 422 responses (validation errors)
document.addEventListener("htmx:beforeSwap", (event) => {
    if (event.detail.xhr.status === 422) {
        event.detail.shouldSwap = true;
        event.detail.isError = false;
    }
});

document.addEventListener("alpine:init", () => {
    // Dropdown menu component (cotton/dropdown-menu.html)
    Alpine.data("dropdownMenu", () => ({
        open: false,
        toggle() {
            this.open = !this.open;
        },
        close() {
            this.open = false;
        },
        positionMenu() {
            if (this.open) {
                const rect = this.$refs.menuButton.getBoundingClientRect();
                const panel = this.$refs.menuPanel;
                if (panel) {
                    const menuWidth = panel.offsetWidth || 160;
                    const menuHeight = panel.offsetHeight;

                    let x = rect.right - menuWidth;
                    let y = rect.bottom + 8;

                    if (x + menuWidth > window.innerWidth) x = window.innerWidth - menuWidth - 8;
                    if (x < 8) x = 8;
                    if (y + menuHeight > window.innerHeight) y = rect.top - menuHeight;

                    panel.style.top = y + "px";
                    panel.style.left = x + "px";
                }
            }
        },
        init() {
            this.$watch("open", () => this.positionMenu());
        },
    }));

    // Modal component (cotton/modal.html)
    Alpine.data("modal", () => ({
        open: false,
        init() {
            const initial = this.$el.dataset.open;
            if (initial === "True" || initial === "true") {
                this.open = true;
            }
            // Close modal when a form inside receives a 204 response (successful save)
            this.$el.addEventListener("htmx:afterRequest", (event) => {
                if (event.detail.xhr && event.detail.xhr.status === 204) {
                    this.open = false;
                }
            });
        },
        show() {
            // Reset any form inside the modal when opening
            const form = this.$el.querySelector("form");
            if (form) form.reset();
            this.open = true;
        },
        close() {
            this.open = false;
        },
        onEscape() {
            this.open = false;
        },
    }));

    // Toast message component (partials/messages.html)
    Alpine.data("message", () => ({
        show: true,
        init() {
            setTimeout(() => {
                this.show = false;
            }, 8000);
        },
        dismiss() {
            this.show = false;
        },
    }));

    // Sidebar component (cotton/sidebar.html)
    Alpine.data("sidebarComponent", () => ({
        sidebarOpen: false,
        isMobile: false,
        _storageKey: "sidebar",
        _mqHandler: null,
        _mq: null,
        init() {
            this._storageKey = this.$el.dataset.storageKey || "sidebar";
            this._mq = window.matchMedia("(min-width: 1024px)");
            this.isMobile = !this._mq.matches;

            const stored = localStorage.getItem(this._storageKey);
            if (stored !== null) {
                this.sidebarOpen = stored === "true";
            } else {
                this.sidebarOpen = this._mq.matches;
            }

            this._mqHandler = (e) => {
                this.isMobile = !e.matches;
                if (e.matches && localStorage.getItem(this._storageKey) === null) {
                    this.sidebarOpen = true;
                }
            };
            this._mq.addEventListener("change", this._mqHandler);

            this.$watch("sidebarOpen", () => this._updateSidebarUI());
            this.$watch("isMobile", () => this._updateSidebarUI());
            this.$nextTick(() => this._updateSidebarUI());
        },
        destroy() {
            if (this._mq && this._mqHandler) {
                this._mq.removeEventListener("change", this._mqHandler);
            }
        },
        toggle() {
            this.sidebarOpen = !this.sidebarOpen;
            localStorage.setItem(this._storageKey, this.sidebarOpen);
        },
        closeSidebar() {
            this.sidebarOpen = false;
            localStorage.setItem(this._storageKey, false);
        },
        _updateSidebarUI() {
            // Update toggle button visibility
            const toggleBtn = this.$el.querySelector("[data-sidebar-toggle]");
            if (toggleBtn) toggleBtn.hidden = this.sidebarOpen;

            // Update backdrop visibility
            const backdrop = this.$el.querySelector("[data-sidebar-backdrop]");
            if (backdrop) backdrop.hidden = !(this.sidebarOpen && this.isMobile);

            // Update sidebar panel classes
            const panel = this.$el.querySelector("[data-sidebar-panel]");
            if (panel) {
                panel.hidden = !this.sidebarOpen;
                if (this.isMobile) {
                    panel.className = "fixed inset-y-0 left-0 z-40 w-64 bg-surface shadow-lg overflow-y-auto p-4";
                } else {
                    panel.className = "relative w-64 shrink-0";
                }
            }
        },
        handleSidebarClick(event) {
            if (this.isMobile && event.target.closest("a")) {
                this.closeSidebar();
            }
        },
        headerBarLeftClass() {
            if (!this.sidebarOpen) return "hidden";
            if (this.isMobile) return "hidden";
            return "w-64 shrink-0 flex items-center justify-between px-4";
        },
        headerBarToggleClass() {
            if (this.sidebarOpen) return "hidden";
            return "";
        },
        sidebarColumnClass() {
            if (this.sidebarOpen && !this.isMobile) return "w-64 shrink-0";
            return "";
        },
        sidebarPanelClass() {
            if (this.isMobile) return "fixed left-0 z-40 w-4/5 max-w-96 bg-surface shadow-lg overflow-y-auto";
            return "";
        },
        backdropVisible() {
            return this.sidebarOpen && this.isMobile;
        },
    }));

    // Course part expand/collapse (student_interface/partials/course_minimal_toc.html)
    Alpine.data("coursePart", () => ({
        expanded: false,
        init() {
            const key = this.$el.dataset.storageKey;
            if (key) {
                this.expanded = localStorage.getItem(key) === "true";
            }
        },
        toggleExpanded() {
            this.expanded = !this.expanded;
            const key = this.$el.dataset.storageKey;
            if (key) {
                localStorage.setItem(key, this.expanded);
            }
        },
    }));

    // Tab container component (panel_framework/partials/tab_container.html)
    Alpine.data("tabContainer", () => ({
        activeTab: "",
        loadedTabs: {},
        baseUrl: "",
        defaultTab: "",
        _popstateHandler: null,
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

            this.$watch("activeTab", () => this._updateTabUI());
            this.$nextTick(() => this._updateTabUI());
        },
        destroy() {
            if (this._popstateHandler) {
                window.removeEventListener("popstate", this._popstateHandler);
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
                    const el = document.getElementById("tab-content-" + name);
                    if (el) htmx.trigger(el, "load-tab");
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

    // Debug branch badge (_base.html)
    Alpine.data("debugBadge", () => ({
        expanded: true,
        init() {
            this.expanded =
                localStorage.getItem("debug-branch-expanded") !== "false";
        },
        toggle() {
            this.expanded = !this.expanded;
            localStorage.setItem("debug-branch-expanded", this.expanded);
        },
        badgeStyle() {
            if (this.expanded) {
                return { padding: "4px 10px", borderRadius: "9999px" };
            }
            return { width: "16px", height: "16px", borderRadius: "50%" };
        },
    }));
});
