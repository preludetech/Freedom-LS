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
});
