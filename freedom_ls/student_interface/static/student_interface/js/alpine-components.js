/**
 * Alpine.js CSP-compatible component registrations for student_interface.
 *
 * Load this script BEFORE the Alpine CSP script via the
 * extra_alpine_components block.
 */

document.addEventListener("alpine:init", () => {
    // Course part expand/collapse (student_interface/partials/course_minimal_toc.html)
    Alpine.data("coursePart", () => ({
        expanded: false,
        storageKey: null,
        init() {
            // Capture the storage key while $el still refers to the root
            // component element. When toggleExpanded is invoked from the
            // button's x-on:click, $el resolves to the button instead.
            this.storageKey = this.$el.dataset.storageKey || null;
            if (this.storageKey) {
                this.expanded = localStorage.getItem(this.storageKey) === "true";
            }
            this.$watch("expanded", () => this._updateUI());
            this.$nextTick(() => this._updateUI());
        },
        toggleExpanded() {
            this.expanded = !this.expanded;
            if (this.storageKey) {
                localStorage.setItem(this.storageKey, this.expanded);
            }
        },
        _updateUI() {
            const icon = this.$el.querySelector("[data-collapse-icon]");
            if (icon) icon.hidden = this.expanded;
        },
    }));

    // Date eyebrow shown above the dashboard greeting
    // (student_interface/dashboard.html). Formats today's date in the
    // browser's own locale and timezone, spelled out (e.g. "Friday, 30 May
    // 2026"). Refreshes when the tab regains visibility so a long-open tab
    // does not show a stale date.
    Alpine.data("dateEyebrow", () => ({
        formatted: "",
        _onVisibility: null,
        init() {
            this._format();
            this._onVisibility = () => {
                if (!document.hidden) this._format();
            };
            document.addEventListener("visibilitychange", this._onVisibility);
        },
        destroy() {
            if (this._onVisibility) {
                document.removeEventListener("visibilitychange", this._onVisibility);
            }
        },
        _format() {
            // undefined locale -> browser locale; no timeZone -> browser timezone.
            this.formatted = new Date().toLocaleDateString(undefined, {
                weekday: "long",
                day: "numeric",
                month: "long",
                year: "numeric",
            });
        },
    }));
});
