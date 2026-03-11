/**
 * Alpine.js CSP-compatible component registrations.
 *
 * The @alpinejs/csp build does not support inline JS expressions.
 * All Alpine components must be registered via Alpine.data().
 * Load this script BEFORE the Alpine CSP script.
 */

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
                const panel = this.$el.querySelector(".dropdown-panel");
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
        },
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

            this.$watch("sidebarOpen", (val) => {
                localStorage.setItem(this._storageKey, val);
            });
        },
        destroy() {
            if (this._mq && this._mqHandler) {
                this._mq.removeEventListener("change", this._mqHandler);
            }
        },
        toggle() {
            this.sidebarOpen = !this.sidebarOpen;
        },
        closeSidebar() {
            this.sidebarOpen = false;
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
