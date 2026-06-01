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
    // On load, scroll the current row of the outline panel into view so the
    // learner can see where they are in a long course. Scoped to the outline's
    // own scroll container (block: "nearest"), so it nudges only that panel,
    // never the main content.
    //
    // It deliberately does NOT move focus to the heading: each player item is a
    // full page load, so the browser already lands at the top and assistive
    // tech reads from there. Programmatic heading focus added no real benefit
    // while forcing a visible focus ring and a scroll jump on every navigation.
    Alpine.data("coursePlayer", () => ({
        init() {
            this.$nextTick(() => {
                const current = document.querySelector(
                    '[aria-label="Course outline"] [aria-current="page"]',
                );
                if (current) current.scrollIntoView({ block: "nearest" });
            });
        },
    }));

    // -------------------------------------------------------------------------
    // Exam runner components
    // -------------------------------------------------------------------------

    // examRunner — root component for the exam runner page.
    //
    // Responsibilities:
    //   - Adds a best-effort `beforeunload` warning while the runner is active
    //     (desktop only; mobile browsers do not reliably fire this event).
    //     IMPORTANT: never call Django endpoints from beforeunload — only
    //     e.preventDefault(). Server-side cleanup at next visit is the real
    //     safety net.
    //   - Focuses the page heading ([data-runner-page-heading]) on load so
    //     screen readers announce page context immediately after navigation.
    Alpine.data("examRunner", () => ({
        _unloadHandler: null,
        init() {
            this._unloadHandler = (e) => {
                e.preventDefault();
            };
            window.addEventListener("beforeunload", this._unloadHandler);

            // Focus the page heading for screen reader context on page load.
            this.$nextTick(() => {
                const heading = document.querySelector("[data-runner-page-heading]");
                if (heading) heading.focus();
            });
        },
        destroy() {
            if (this._unloadHandler) {
                window.removeEventListener("beforeunload", this._unloadHandler);
                this._unloadHandler = null;
            }
        },
    }));

    // confirmDialog — shared focus-trap factory backing the exit and submit
    // dialogs. Both examExitDialog and examSubmitDialog delegate to this
    // pattern: open state, focus trap, focus return to trigger, Escape-to-close.
    //
    // Template usage:
    //   x-data="examExitDialog"  or  x-data="examSubmitDialog"
    //
    // Public API shared by both:
    //   open          — boolean; bind x-show on dialog panel, x-cloak on panel
    //   _triggerEl    — element that opened the dialog; focus returns here on close
    //   _focusTrap    — internal keydown handler; cleaned up on close/destroy
    //
    // Internal helper (inlined into each concrete component below).
    function makeConfirmDialog(extraProps) {
        return () => ({
            open: false,
            _triggerEl: null,
            _focusTrap: null,

            _openDialog(triggerEl) {
                this._triggerEl = triggerEl || null;
                this.open = true;
                this.$nextTick(() => {
                    const focusable = Array.from(
                        this.$el.querySelectorAll(
                            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
                        )
                    );
                    if (focusable.length) focusable[0].focus();
                    this._focusTrap = (e) => {
                        if (e.key !== "Tab") return;
                        const first = focusable[0];
                        const last = focusable[focusable.length - 1];
                        if (e.shiftKey && document.activeElement === first) {
                            e.preventDefault();
                            last.focus();
                        } else if (!e.shiftKey && document.activeElement === last) {
                            e.preventDefault();
                            first.focus();
                        }
                    };
                    this.$el.addEventListener("keydown", this._focusTrap);
                });
            },

            _closeDialog() {
                this.open = false;
                if (this._focusTrap) {
                    this.$el.removeEventListener("keydown", this._focusTrap);
                    this._focusTrap = null;
                }
                if (this._triggerEl) {
                    this._triggerEl.focus();
                    this._triggerEl = null;
                }
            },

            destroy() {
                this._closeDialog();
            },

            ...extraProps,
        });
    }

    // examExitDialog — exit confirmation dialog (top-bar X button).
    //
    // Template wires:
    //   x-data="examExitDialog" on the wrapper that contains the trigger + panel
    //   x-on:click="showExit"   on the exit (X) button; pass $el as the trigger
    //   x-on:click="dismiss"    on the "Keep going" / cancel button
    //   x-on:keydown.escape.window="dismiss"  on the dialog panel
    //   x-show="open"  x-cloak  on the dialog panel
    //
    // The confirm action (Leave and submit, or navigate away) is a plain form
    // POST or anchor — no Alpine method needed for it.
    Alpine.data("examExitDialog", makeConfirmDialog({
        showExit(triggerEl) {
            this._openDialog(triggerEl);
        },
        dismiss() {
            this._closeDialog();
        },
    }));

    // examSubmitDialog — review/submit confirmation dialog (final-page Next button).
    //
    // Template wires:
    //   x-data="examSubmitDialog" on the wrapper that contains the trigger + panel
    //   x-on:click="openSubmitDialog"  on the "Next" button on the final page
    //   x-on:click="closeSubmitDialog" on the "Go back and review" button
    //   x-on:keydown.escape.window="closeSubmitDialog"  on the dialog panel
    //   x-show="open"  x-cloak  on the dialog panel
    //   x-on:click="submit($refs.pageForm)"  on the Submit button
    //   x-bind:disabled="submitting"  on the Submit button
    //
    // The pageForm $ref must be set on the <form> element in the runner template.
    Alpine.data("examSubmitDialog", makeConfirmDialog({
        submitting: false,

        openSubmitDialog(triggerEl) {
            this._openDialog(triggerEl);
        },
        closeSubmitDialog() {
            this._closeDialog();
        },

        // Guard against double-submit on slow networks.
        // formEl is the <form> element passed from the template via $refs.
        submit(formEl) {
            if (this.submitting) return;
            this.submitting = true;
            formEl.submit();
        },
    }));

    // -------------------------------------------------------------------------
    // End exam runner components
    // -------------------------------------------------------------------------

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
