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

            const top = this.$el.getBoundingClientRect().top;
            this.$el.style.setProperty("--sidebar-top", top + "px");

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

            this.$watch("sidebarOpen", (val) => localStorage.setItem(this._storageKey, val));
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

    // Scroll table with floating row labels on mobile (cotton/scroll-table-labels.html)
    Alpine.data("scrollTableLabels", () => ({
        scrolledPastFirst: false,
        firstColWidth: 0,
        _scrollHandler: null,
        _resizeObserver: null,
        _resizeTimeout: null,
        _mq: null,
        _mqHandler: null,
        _rafId: null,
        _active: false,
        _headerSelector: "thead th",
        _cellSelector: "td",
        init() {
            const container = this.$refs.scrollTableContainer;
            const overlay = this.$refs.scrollTableOverlay;
            if (!container || !overlay) return;

            this._headerSelector = this.$el.dataset.headerSelector || "thead th";
            this._cellSelector = this.$el.dataset.cellSelector || "td";

            this._mq = window.matchMedia("(min-width: 768px)");
            this._mqHandler = (e) => {
                if (e.matches) {
                    this._teardownLabels(container, overlay);
                } else {
                    this._setupLabels(container, overlay);
                }
            };
            this._mq.addEventListener("change", this._mqHandler);

            if (!this._mq.matches) {
                this._setupLabels(container, overlay);
            }
        },
        destroy() {
            const container = this.$refs.scrollTableContainer;
            const overlay = this.$refs.scrollTableOverlay;
            if (this._mq && this._mqHandler) {
                this._mq.removeEventListener("change", this._mqHandler);
            }
            if (container && overlay) this._teardownLabels(container, overlay);
        },
        _setupLabels(container, overlay) {
            if (this._active) return;
            this._active = true;

            const firstTh = container.querySelector(this._headerSelector);
            if (firstTh) this.firstColWidth = firstTh.offsetWidth;

            this._scrollHandler = () => {
                const scrolled = container.scrollLeft > this.firstColWidth;
                if (scrolled !== this.scrolledPastFirst) {
                    this.scrolledPastFirst = scrolled;
                    overlay.classList.toggle("hidden", !scrolled);
                }
                if (scrolled) {
                    overlay.style.top = -container.scrollTop + "px";
                }
            };
            container.addEventListener("scroll", this._scrollHandler);

            this._rafId = requestAnimationFrame(() => this._buildLabels(container, overlay));

            this._resizeObserver = new ResizeObserver(() => {
                clearTimeout(this._resizeTimeout);
                this._resizeTimeout = setTimeout(() => {
                    this._rafId = requestAnimationFrame(() => this._buildLabels(container, overlay));
                }, 150);
            });
            this._resizeObserver.observe(container);
        },
        _teardownLabels(container, overlay) {
            if (!this._active) return;
            this._active = false;
            this.scrolledPastFirst = false;

            if (this._scrollHandler) {
                container.removeEventListener("scroll", this._scrollHandler);
                this._scrollHandler = null;
            }
            if (this._resizeObserver) {
                this._resizeObserver.disconnect();
                this._resizeObserver = null;
            }
            clearTimeout(this._resizeTimeout);
            if (this._rafId) {
                cancelAnimationFrame(this._rafId);
                this._rafId = null;
            }
            overlay.innerHTML = "";
            overlay.classList.add("hidden");
        },
        _buildLabels(container, overlay) {
            overlay.innerHTML = "";
            const containerRect = container.getBoundingClientRect();
            container.querySelectorAll("tbody tr").forEach((tr) => {
                const firstCell = tr.querySelector(this._cellSelector);
                if (!firstCell) return;
                const text = firstCell.textContent.trim();
                if (!text) return;

                const label = document.createElement("div");
                label.textContent = text;
                label.className = "text-xs font-medium whitespace-nowrap bg-surface-2 text-foreground px-1.5 py-0.5 rounded shadow-sm";
                const rowRect = tr.getBoundingClientRect();
                label.style.cssText = "position:absolute; left:4px; top:" + (rowRect.top - containerRect.top + container.scrollTop) + "px;";
                overlay.appendChild(label);
            });
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
