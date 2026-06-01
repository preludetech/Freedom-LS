/**
 * Alpine.js CSP-compatible component registrations.
 *
 * The @alpinejs/csp build does not support inline JS expressions.
 * All Alpine components must be registered via Alpine.data().
 * Load this script BEFORE the Alpine CSP script.
 */

// Allow HTMX to swap content on 422 responses (validation errors), and
// on any other 4xx/5xx response that contains an OOB toast fragment so
// server-rendered messages still surface on errors.
document.addEventListener("htmx:beforeSwap", (event) => {
    const status = event.detail.xhr.status;
    if (status === 422) {
        event.detail.shouldSwap = true;
        event.detail.isError = false;
        return;
    }
    if (status >= 400 && status < 600) {
        const body = event.detail.xhr.responseText || "";
        if (body.includes('hx-swap-oob="beforeend:#toast-region-')) {
            // Process the OOB toast fragment. Leave isError truthful so
            // any other listeners still see the actual error status.
            event.detail.shouldSwap = true;
        }
    }
});

document.addEventListener("alpine:init", () => {
    // Sticky-header scroll state (partials/header_bar.html).
    //
    // Exposes a single boolean `scrolled` reflecting `window.scrollY > 0`,
    // which the template binds to `data-scrolled` so theme CSS can swap
    // surface treatments (stronger shadow in default, translucent frosted
    // glass in first_class) without per-theme template branches.
    //
    // Listener is passive and cheap. The change-detection guard means the
    // attribute only re-renders when the boolean state actually flips, so
    // no class thrash on every scroll tick.
    Alpine.data("headerScroll", () => ({
        scrolled: false,
        _onScroll: null,
        init() {
            this._onScroll = () => {
                const next = window.scrollY > 0;
                if (next !== this.scrolled) this.scrolled = next;
            };
            // Set initial state for back-button restore / mid-page loads.
            this._onScroll();
            window.addEventListener("scroll", this._onScroll, { passive: true });
        },
        destroy() {
            if (this._onScroll) {
                window.removeEventListener("scroll", this._onScroll);
                this._onScroll = null;
            }
        },
    }));

    // Dropdown menu component (cotton/dropdown-menu.html)
    Alpine.data("dropdownMenu", () => ({
        open: false,
        toggle() {
            this.open = !this.open;
        },
        close() {
            this.open = false;
        },
        onEscape() {
            if (!this.open) return;
            this.open = false;
            if (this.$refs.menuButton) {
                this.$refs.menuButton.focus();
            }
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

    // Shared <dialog> overlay controller (cotton/overlay.html).
    //
    // Wraps a native <dialog>. open(triggerEl) calls showModal() so the browser
    // gives us a focus trap, background inertness, Escape-to-close, and a
    // ::backdrop scrim for free. close() calls dialog.close(). On the dialog's
    // native "close" event (covers Escape and device Back) we restore focus to
    // the trigger and dispatch "overlay-closed" so an external trigger can sync
    // aria-expanded. A click that lands on the dialog element itself (i.e. the
    // backdrop region, not the panel) also closes.
    Alpine.data("overlayDialog", () => ({
        triggerEl: null,
        init() {
            this.dialog = this.$refs.dialog;
            this.dialog.addEventListener("close", () => {
                this.$dispatch("overlay-closed");
                if (this.triggerEl) this.triggerEl.focus();
            });
            this.dialog.addEventListener("click", (event) => {
                if (event.target === this.dialog) this.close();
            });
        },
        open(eventOrEl) {
            // Called either directly with a trigger element or from x-on:click
            // (which passes an Event). Resolve the triggering element so focus
            // can be restored to it on close.
            if (eventOrEl instanceof Event) {
                this.triggerEl = eventOrEl.currentTarget;
            } else {
                this.triggerEl = eventOrEl || null;
            }
            this.dialog.showModal();
        },
        close() {
            this.dialog.close();
        },
    }));

    // Toast component (partials/_toast.html).
    //
    // Per-severity timing:
    //   success / info / debug -> 5000 ms
    //   warning                -> 7000 ms
    //   error                  -> persistent (no auto-dismiss)
    //
    // The dismiss timer pauses on hover, on keyboard focus inside the toast,
    // and while the window has lost focus. Pause/resume preserves the
    // remaining time rather than restarting the timer from zero.
    //
    // Soft cap: at most 5 visible non-error toasts. When this toast is the
    // 6th non-error, the oldest non-error in either ARIA region is dismissed.
    // If 5 errors are already visible and this is a non-error, this toast is
    // dropped silently.
    Alpine.data("toast", () => ({
        show: true,
        _timeoutId: null,
        _remainingMs: 0,
        _startedAt: 0,
        _paused: false,
        _windowBlurHandler: null,
        _windowFocusHandler: null,

        init() {
            const severity = this.$el.dataset.severity || "info";

            // Soft-cap eviction must run before we install timers / show.
            if (this._enforceCap(severity)) {
                // This toast was dropped (non-error and 5 errors are visible).
                return;
            }

            const duration = this._durationFor(severity);
            if (duration === null) {
                // Errors are persistent. No timer, no window listeners.
                return;
            }
            this._remainingMs = duration;
            this._start();

            this._windowBlurHandler = () => this._pause();
            this._windowFocusHandler = () => this._resume();
            window.addEventListener("blur", this._windowBlurHandler);
            window.addEventListener("focus", this._windowFocusHandler);
        },

        destroy() {
            if (this._timeoutId !== null) {
                clearTimeout(this._timeoutId);
                this._timeoutId = null;
            }
            if (this._windowBlurHandler) {
                window.removeEventListener("blur", this._windowBlurHandler);
                this._windowBlurHandler = null;
            }
            if (this._windowFocusHandler) {
                window.removeEventListener("focus", this._windowFocusHandler);
                this._windowFocusHandler = null;
            }
        },

        onMouseEnter() {
            this._pause();
        },
        onMouseLeave() {
            this._resume();
        },
        onFocusIn() {
            this._pause();
        },
        onFocusOut() {
            // Resume only if focus actually left this toast.
            if (!this.$el.contains(document.activeElement)) {
                this._resume();
            }
        },
        onKeydown(event) {
            if (event.key === "Escape" && this.$el.contains(document.activeElement)) {
                this.dismiss();
            }
        },

        dismiss() {
            if (this._timeoutId !== null) {
                clearTimeout(this._timeoutId);
                this._timeoutId = null;
            }
            this.show = false;
            // Wait for the leave transition (~150ms) then remove from the DOM
            // so the live regions stay tidy and the cap accounting is accurate.
            // Use $root (not $el) so the toast root is removed even when
            // dismiss() fires from a click on the close button — Alpine binds
            // $el to the listener's element, but $root always points at the
            // x-data root.
            const root = this.$root;
            setTimeout(() => {
                if (root && root.parentNode) {
                    root.remove();
                }
            }, 200);
        },

        _durationFor(severity) {
            if (severity === "warning") return 7000;
            if (severity === "error") return null;
            return 5000;
        },

        _start() {
            this._startedAt = Date.now();
            this._paused = false;
            this._timeoutId = setTimeout(() => this.dismiss(), this._remainingMs);
        },

        _pause() {
            if (this._paused || this._timeoutId === null) return;
            this._paused = true;
            clearTimeout(this._timeoutId);
            this._timeoutId = null;
            this._remainingMs -= Date.now() - this._startedAt;
            if (this._remainingMs < 0) this._remainingMs = 0;
        },

        _resume() {
            if (!this._paused) return;
            if (this._remainingMs <= 0) {
                this.dismiss();
                return;
            }
            this._start();
        },

        // Enforce the soft cap. Returns true if this toast was dropped.
        _enforceCap(severity) {
            const polite = document.getElementById("toast-region-polite");
            const assertive = document.getElementById("toast-region-assertive");
            // Visible non-error toasts (live in the polite region) and errors
            // (live in the assertive region). $el is already in the DOM here.
            const nonErrorEls = polite ? Array.from(polite.children) : [];
            const errorCount = assertive ? assertive.children.length : 0;

            // If 5 errors are already visible and this is a non-error, drop it.
            if (severity !== "error" && errorCount >= 5) {
                this.show = false;
                if (this.$el && this.$el.parentNode) {
                    this.$el.remove();
                }
                return true;
            }

            // Cap non-error toasts at 5. If this is a non-error and we are now
            // over the cap, evict the oldest non-error from the polite region.
            // Children are appended in DOM order; oldest is the first child,
            // which is also visually furthest from the viewport edge under
            // flex-col (newest at the bottom).
            if (severity !== "error") {
                while (nonErrorEls.length > 5) {
                    const oldest = nonErrorEls.shift();
                    if (!oldest || oldest === this.$el) continue;
                    this._dismissSibling(oldest);
                }
            }
            return false;
        },

        _dismissSibling(el) {
            // Try to invoke the sibling toast's dismiss() so its timer is
            // cleared and its leave transition runs. Fall back to direct
            // removal if Alpine isn't available on the element.
            const data = window.Alpine && window.Alpine.$data ? window.Alpine.$data(el) : null;
            if (data && typeof data.dismiss === "function") {
                data.dismiss();
                return;
            }
            el.remove();
        },
    }));

    // Unified side panel (base/_base_interface.html).
    //
    // One <dialog> drives every sidebar in the app (student course TOC,
    // educator nav, panel_framework nav). The presentation differs per consumer
    // (bottom-sheet vs side-drawer, set via a data attribute) but the mechanism
    // is identical:
    //
    //   - Desktop (lg+): the dialog is opened NON-modally with dialog.show() so
    //     it renders in-flow as a persistent docked column (no inertness, no
    //     scrim) and coexists with the page. Open/closed state persists to
    //     localStorage under data-storage-key (preserving the existing keys).
    //   - Below lg: the dialog is opened with dialog.showModal() so it becomes a
    //     modal overlay with a scrim, an inert background, a focus trap,
    //     Escape-to-close, and device-Back dismissal — all native to <dialog>.
    //
    // aria-expanded on the toggle is bound to `open`; the dialog's native
    // "close" event syncs it back and returns focus to the toggle.
    Alpine.data("sidePanel", () => ({
        open: false,
        isMobile: false,
        _storageKey: "sidebar",
        _mq: null,
        _mqHandler: null,
        triggerEl: null,
        init() {
            this.dialog = this.$refs.panelDialog;
            this._storageKey = this.$el.dataset.storageKey || "sidebar";
            this._mq = window.matchMedia("(min-width: 1024px)");
            this.isMobile = !this._mq.matches;

            // Position the docked panel below the header bar (consumed by the
            // CSS var on the dialog). Carried over from the old sidebar.
            const top = this.$el.getBoundingClientRect().top;
            this.$el.style.setProperty("--sidebar-top", top + "px");

            this.dialog.addEventListener("close", () => {
                this.open = false;
                if (this.triggerEl) this.triggerEl.focus();
            });
            this.dialog.addEventListener("click", (event) => {
                // A click on the dialog element itself (the modal backdrop) closes.
                if (event.target === this.dialog && this.isMobile) this.close();
            });

            // On desktop, default to the persisted state (open if never set).
            // On mobile, always start collapsed.
            const stored = localStorage.getItem(this._storageKey);
            if (!this.isMobile) {
                this._setDesktopOpen(stored === null ? true : stored === "true");
            }

            this._mqHandler = (e) => {
                const wasMobile = this.isMobile;
                this.isMobile = !e.matches;
                if (wasMobile === this.isMobile) return;
                // Reset to the correct mode for the new breakpoint.
                if (this.dialog.open) this.dialog.close();
                this.open = false;
                if (!this.isMobile) {
                    const desktopStored = localStorage.getItem(this._storageKey);
                    this._setDesktopOpen(
                        desktopStored === null ? true : desktopStored === "true",
                    );
                }
            };
            this._mq.addEventListener("change", this._mqHandler);
        },
        destroy() {
            if (this._mq && this._mqHandler) {
                this._mq.removeEventListener("change", this._mqHandler);
            }
        },
        _setDesktopOpen(value) {
            this.open = value;
            if (value && !this.dialog.open) {
                this.dialog.show();
            } else if (!value && this.dialog.open) {
                this.dialog.close();
            }
        },
        toggle(event) {
            this.triggerEl = (event && event.currentTarget) || null;
            if (this.isMobile) {
                if (this.dialog.open) {
                    this.close();
                } else {
                    this.open = true;
                    this.dialog.showModal();
                }
            } else {
                this._setDesktopOpen(!this.open);
                localStorage.setItem(this._storageKey, this.open);
            }
        },
        close() {
            if (this.dialog.open) this.dialog.close();
            this.open = false;
            if (!this.isMobile) {
                localStorage.setItem(this._storageKey, false);
            }
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
                label.className = "text-xs font-medium whitespace-nowrap bg-surface-2 text-on-surface px-1.5 py-0.5 rounded shadow-sm";
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
