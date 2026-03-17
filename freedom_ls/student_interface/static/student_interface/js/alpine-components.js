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
        init() {
            const key = this.$el.dataset.storageKey;
            if (key) {
                this.expanded = localStorage.getItem(key) === "true";
            }
            this.$watch("expanded", () => this._updateUI());
            this.$nextTick(() => this._updateUI());
        },
        toggleExpanded() {
            this.expanded = !this.expanded;
            const key = this.$el.dataset.storageKey;
            if (key) {
                localStorage.setItem(key, this.expanded);
            }
        },
        _updateUI() {
            const icon = this.$el.querySelector("[data-collapse-icon]");
            if (icon) icon.hidden = this.expanded;
        },
    }));
});
