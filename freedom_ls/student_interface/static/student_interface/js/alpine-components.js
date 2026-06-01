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
            // Auto-expand the part that contains the current item, without
            // writing to localStorage — so a part the learner manually
            // collapsed elsewhere keeps its stored state, and this auto-expand
            // does not clobber their choices.
            if (this.$el.dataset.containsCurrent === "true") {
                this.expanded = true;
                this._scrollCurrentIntoView();
            }
            this.$watch("expanded", () => this._updateUI());
            this.$nextTick(() => this._updateUI());
        },
        _scrollCurrentIntoView() {
            this.$nextTick(() => {
                const current = this.$el.querySelector('[aria-current="page"]');
                if (current) current.scrollIntoView({ block: "nearest" });
            });
        },
        toggleExpanded() {
            this.expanded = !this.expanded;
            if (this.storageKey) {
                localStorage.setItem(this.storageKey, this.expanded);
            }
        },
        _updateUI() {
            const icon = this.$el.querySelector("[data-toggle-icon]");
            if (icon) icon.hidden = this.expanded;
        },
    }));

    // Course player content region (course_topic.html / course_form.html ...).
    //
    // On load, move focus to the content heading (so keyboard / screen-reader
    // users land on the new content rather than the top of the page) and scroll
    // any current TOC row into view. The heading carries tabindex="-1" so it is
    // programmatically focusable without entering the tab order.
    Alpine.data("coursePlayer", () => ({
        init() {
            this.$nextTick(() => {
                const heading = this.$el.querySelector("h1");
                if (heading) heading.focus();
                const current = document.querySelector(
                    '[aria-label="Course outline"] [aria-current="page"]',
                );
                if (current) current.scrollIntoView({ block: "nearest" });
            });
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
