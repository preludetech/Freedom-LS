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
        // localStorage key used to persist sidebar open/closed state across page loads
        _storageKey: "sidebar",
        // Bound reference to the media-query change callback, kept so we can removeEventListener in destroy()
        _mqHandler: null,
        // matchMedia instance for the lg (1024px) breakpoint, used to detect mobile vs desktop
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

    // Picture modal component (cotton/picture.html)
    Alpine.data("pictureModal", () => ({
        open: false,
        show() {
            this.open = true;
        },
        close() {
            this.open = false;
        },
        onEscape() {
            this.open = false;
        },
    }));

    // Debug branch badge (_base.html)
    Alpine.data("debugBadge", () => ({
        expanded: true,
        init() {
            this.expanded =
                localStorage.getItem("debug-branch-expanded") !== "false";
            this.$watch("expanded", () => this._applyStyle());
            this.$nextTick(() => this._applyStyle());
        },
        toggle() {
            this.expanded = !this.expanded;
            localStorage.setItem("debug-branch-expanded", this.expanded);
        },
        _applyStyle() {
            const el = this.$el;
            if (this.expanded) {
                el.style.padding = "4px 10px";
                el.style.borderRadius = "9999px";
                el.style.width = "";
                el.style.height = "";
            } else {
                el.style.padding = "";
                el.style.width = "16px";
                el.style.height = "16px";
                el.style.borderRadius = "50%";
            }
        },
    }));
});
