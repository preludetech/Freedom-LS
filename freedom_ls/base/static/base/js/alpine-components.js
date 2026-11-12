/**
 * Alpine.js CSP-compatible component registrations.
 *
 * The @alpinejs/csp build does not support inline JS expressions.
 * All Alpine components must be registered via Alpine.data().
 * Load this script BEFORE the Alpine CSP script.
 */

// Allow HTMX to swap content on 422 responses (validation errors), on 403 and
// 404 fragments marked data-htmx-swap-error (an action the user's role no
// longer allows, or whose object has left the user's scope), and on any other
// 4xx/5xx response that contains an OOB toast fragment so server-rendered
// messages still surface on errors. An unmarked 403 or 404 is a full page and
// is never swapped in. What happens to it instead is the interface's call:
// the panel framework's script reloads the page, and a page with a form the
// user may be filling in leaves it alone.
document.addEventListener("htmx:beforeSwap", (event) => {
    const status = event.detail.xhr.status;
    const body = event.detail.xhr.responseText || "";
    if (
        status === 422 ||
        ((status === 403 || status === 404) &&
            body.includes("data-htmx-swap-error"))
    ) {
        event.detail.shouldSwap = true;
        event.detail.isError = false;
        return;
    }
    if (status >= 400 && status < 600) {
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

    // Hands a click to the stretched title link of the surrounding card or row
    // (cotton/organisation-byline.html). The organisation name sits above that
    // link so its title tooltip can show, which would otherwise swallow the
    // click.
    Alpine.data("stretchedLinkProxy", () => ({
        open() {
            const link = this.$el.closest("article")?.querySelector("a");
            if (link) link.click();
        },
    }));

    // Dropdown menu component (cotton/dropdown-menu.html)
    Alpine.data("dropdownMenu", () => ({
        open: false,
        scrollYAtOpen: 0,
        toggle(event) {
            if (this.open) {
                this.close();
                return;
            }
            this.open = true;
            // A click synthesised by Enter or Space carries detail 0. Only a
            // keyboard open moves focus into the menu; a pointer open leaves
            // focus on the trigger so the pointer stays in charge.
            if (event && event.detail === 0) {
                this.focusInitialItem();
            }
        },
        openFromTrigger() {
            this.open = true;
            this.focusInitialItem();
        },
        close() {
            this.open = false;
        },
        // A scroll event is delivered a frame after the scroll itself, so a
        // trigger the browser scrolled into view for the click would close
        // the menu it had just opened. Only a scroll that moves the page
        // away from where it was at open closes the menu.
        closeOnScroll() {
            if (window.scrollY === this.scrollYAtOpen) return;
            this.close();
        },
        // Menu items keep their natural tab stop, so Tab still walks the menu
        // in DOM order; the arrow keys are an addition to that, not a
        // replacement for it.
        menuItems() {
            const panel = this.$refs.menuPanel;
            if (!panel) return [];
            const items = panel.querySelectorAll(
                '[role="menuitem"], [role="menuitemradio"], [role="menuitemcheckbox"]'
            );
            return Array.from(items).filter((item) => !item.disabled);
        },
        focusInitialItem() {
            const items = this.menuItems();
            if (items.length === 0) return;
            const checked = items.find(
                (item) => item.getAttribute("aria-checked") === "true"
            );
            const trigger = this.$refs.menuButton;
            // x-show only reveals the panel on the next tick; a hidden element
            // cannot take focus. By then the user may already have tabbed on,
            // so only take focus if it is still sitting on the trigger.
            this.$nextTick(() => {
                if (document.activeElement !== trigger) return;
                (checked || items[0]).focus();
            });
        },
        focusFirstItem() {
            const items = this.menuItems();
            if (items.length > 0) items[0].focus();
        },
        focusLastItem() {
            const items = this.menuItems();
            if (items.length > 0) items[items.length - 1].focus();
        },
        focusNextItem() {
            this.moveFocus(1);
        },
        focusPreviousItem() {
            this.moveFocus(-1);
        },
        moveFocus(step) {
            const items = this.menuItems();
            if (items.length === 0) return;
            const current = items.indexOf(document.activeElement);
            if (current === -1) {
                // Focus is still on the trigger: enter the menu from the end
                // the arrow points at.
                (step > 0 ? items[0] : items[items.length - 1]).focus();
                return;
            }
            items[(current + step + items.length) % items.length].focus();
        },
        // preventDefault() marks this Escape as consumed so any other
        // layer listening for it (e.g. panel_framework's quick-view
        // drawer) knows not to treat the same keypress as its own
        // dismissal. Capture-phase registration (see dropdown-menu.html)
        // runs this before any bubble-phase listener gets to inspect
        // event.defaultPrevented.
        onEscape(event) {
            if (!this.open) return;
            this.open = false;
            if (event) event.preventDefault();
            if (this.$refs.menuButton) {
                this.$refs.menuButton.focus();
            }
        },
        positionMenu() {
            if (this.open) {
                const rect = this.$refs.menuButton.getBoundingClientRect();
                const panel = this.$refs.menuPanel;
                if (panel) {
                    const gap = 8;
                    panel.style.maxHeight = "";
                    panel.style.overflowY = "";
                    // A panel laid out in flow (the organisation switcher inside
                    // the phone navigation sheet) is placed by the page, not here.
                    if (getComputedStyle(panel).position !== "fixed") return;
                    const menuWidth = panel.offsetWidth || 160;
                    const menuHeight = panel.offsetHeight;
                    const spaceBelow = window.innerHeight - rect.bottom - 2 * gap;
                    const spaceAbove = rect.top - 2 * gap;

                    let x = rect.right - menuWidth;
                    if (x + menuWidth > window.innerWidth) x = window.innerWidth - menuWidth - gap;
                    if (x < gap) x = gap;

                    // Below when it fits, above when only that fits; when neither
                    // does, the roomier side gets a capped, scrolling panel so no
                    // item ends up off-screen.
                    let y;
                    if (menuHeight <= spaceBelow || spaceBelow >= spaceAbove) {
                        y = rect.bottom + gap;
                        if (menuHeight > spaceBelow) {
                            panel.style.maxHeight = spaceBelow + "px";
                            panel.style.overflowY = "auto";
                        }
                    } else {
                        const height = Math.min(menuHeight, spaceAbove);
                        if (menuHeight > spaceAbove) {
                            panel.style.maxHeight = spaceAbove + "px";
                            panel.style.overflowY = "auto";
                        }
                        y = rect.top - height - gap;
                    }

                    panel.style.top = y + "px";
                    panel.style.left = x + "px";
                }
            }
        },
        init() {
            // The panel is still display:none when the watcher fires, so it has no
            // height to flip against until the next tick.
            this.$watch("open", (isOpen) => {
                if (isOpen) this.scrollYAtOpen = window.scrollY;
                this.$nextTick(() => this.positionMenu());
            });
            // Options that hx-get into a target outside this dropdown (e.g.
            // the organisation switcher, whose options swap #main-content
            // while the dropdown itself lives in the sidebar) leave the
            // panel visually open after the swap — nothing else closes it.
            // Every other dropdown option navigates away or reloads the
            // page, so this is a no-op for them.
            this.$el.addEventListener("htmx:afterRequest", () => {
                this.close();
            });
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

    // Rewrites a <time> element into the viewer's own zone, as "3 Nov 2026, 07:37"
    // whatever the browser's locale. The server text stays in place when the
    // instant does not parse.
    Alpine.data("localTime", () => ({
        init() {
            const instant = new Date(this.$el.getAttribute("datetime"));
            if (Number.isNaN(instant.getTime())) return;
            const showZone = this.$el.dataset.showZone === "true";
            // en-US parts in a fixed order, so every browser locale reads "3 Nov 2026, 07:37".
            const parts = (options) => {
                const found = {};
                for (const part of new Intl.DateTimeFormat("en-US", options).formatToParts(instant)) {
                    found[part.type] = part.value;
                }
                return found;
            };
            const timeOptions = { hour: "2-digit", minute: "2-digit", hourCycle: "h23" };
            if (showZone) timeOptions.timeZoneName = "short";
            const timeText = () => {
                const time = parts(timeOptions);
                return `${time.hour}:${time.minute}` + (showZone ? ` ${time.timeZoneName}` : "");
            };
            if (this.$el.dataset.format !== "short") {
                const date = parts({ day: "numeric", month: "short", year: "numeric" });
                this.$el.textContent = `${date.day} ${date.month} ${date.year}, ${timeText()}`;
                return;
            }
            // A short date is "Today" on the viewer's own date, and names its year only
            // when it is not the viewer's current year. A deadline with a set time
            // (data-timed) adds it; one given as a date alone shows no time.
            const now = new Date();
            const date = parts({ day: "numeric", month: "short", year: "numeric" });
            let text = `${date.day} ${date.month}`;
            if (instant.getFullYear() !== now.getFullYear()) text += ` ${date.year}`;
            if (instant.toDateString() === now.toDateString()) text = "Today";
            if (this.$el.dataset.timed === "true") text += `, ${timeText()}`;
            this.$el.textContent = text;
        },
    }));

    // Drop zone around a native file input. The label stays a working label
    // for the input, so clicking it or tabbing to the input and pressing
    // Enter opens the picker without any of this. Dragging adds the drop
    // path: the dropped file is handed to the input through a DataTransfer,
    // so the form submits it like a picked one.
    Alpine.data("fileDropZone", () => ({
        dragging: false,
        fileName: "",
        fileSize: "",
        init() {
            this.readInput();
        },
        input() {
            return this.$el.querySelector('input[type="file"]');
        },
        enter() {
            this.dragging = true;
        },
        // dragleave fires when the pointer crosses into a child of the label
        // too; only a leave to outside the label ends the drag-over state.
        leave(event) {
            if (!event.currentTarget.contains(event.relatedTarget)) this.dragging = false;
        },
        drop(event) {
            this.dragging = false;
            const files = event.dataTransfer && event.dataTransfer.files;
            if (!files || files.length === 0) return;
            const transfer = new DataTransfer();
            transfer.items.add(files[0]);
            const input = this.input();
            input.files = transfer.files;
            input.dispatchEvent(new Event("change", { bubbles: true }));
        },
        readInput() {
            const file = this.input().files[0];
            this.fileName = file ? file.name : "";
            this.fileSize = file ? this.formatSize(file.size) : "";
        },
        formatSize(bytes) {
            let size = bytes;
            for (const unit of ["bytes", "KB", "MB"]) {
                if (size < 1024 || unit === "MB") {
                    return unit === "bytes" ? `${size} ${unit}` : `${size.toFixed(1)} ${unit}`;
                }
                size /= 1024;
            }
        },
        hasFile() {
            return this.fileName !== "";
        },
        showPrompt() {
            return !this.dragging && !this.hasFile();
        },
        showFile() {
            return !this.dragging && this.hasFile();
        },
        zoneClass() {
            return this.dragging
                ? "border-solid border-primary bg-surface"
                : "border-dashed border-border bg-surface-2";
        },
    }));
});
