/**
 * Alpine.js CSP-compatible component registrations for student_interface.
 *
 * Load this script BEFORE the Alpine CSP script via the
 * extra_alpine_components block.
 */

document.addEventListener("alpine:init", () => {
    // Shared between examRunner (owns the beforeunload guard) and examRunnerForm
    // (owns submit). Set true when the user triggers a DELIBERATE in-runner
    // navigation (Next / Previous / Submit / exit) so the beforeunload warning
    // does not fire for it — the warning is only meant to catch accidental
    // leaves (closing the tab, typing a new URL).
    let runnerNavigating = false;

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
        _navHandler: null,
        init() {
            // Warn only on accidental leaves — skip deliberate in-runner
            // navigation, which sets runnerNavigating (see below + submit()).
            this._unloadHandler = (e) => {
                if (runnerNavigating) return;
                e.preventDefault();
            };
            window.addEventListener("beforeunload", this._unloadHandler);

            // Mark deliberate in-runner navigations so the beforeunload guard
            // does not fire for them. Capture phase so the flag is set before
            // the navigation begins. Covers Next (form submit), Submit-on-exit
            // (form submit), and Previous / Leave-and-save (anchor clicks).
            // The programmatic Submit path goes through examRunnerForm.submit(),
            // which sets the flag directly (form.submit() fires no submit event).
            this._navHandler = (e) => {
                if (e.type === "submit") {
                    runnerNavigating = true;
                    return;
                }
                if (e.target.closest && e.target.closest("a[href]")) {
                    runnerNavigating = true;
                }
            };
            document.addEventListener("submit", this._navHandler, true);
            document.addEventListener("click", this._navHandler, true);

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
            if (this._navHandler) {
                document.removeEventListener("submit", this._navHandler, true);
                document.removeEventListener("click", this._navHandler, true);
                this._navHandler = null;
            }
            runnerNavigating = false;
        },
    }));

    // confirmDialog — shared focus-trap factory backing the exit and submit
    // dialogs. Both examExitDialog and examRunnerForm delegate to this
    // pattern: open state, focus trap, focus return to trigger, Escape-to-close.
    //
    // Template usage:
    //   x-data="examExitDialog"  or  x-data="examRunnerForm"
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
            _trapEl: null,

            _openDialog(triggerEl) {
                this._triggerEl = triggerEl || null;
                this.open = true;
                this.$nextTick(() => {
                    // Scope focus to the dialog panel, not the whole component.
                    // examRunnerForm wraps the entire runner, so trapping on
                    // $el would span every runner control; the panel ref keeps
                    // the trap inside the open dialog. Falls back to $el for any
                    // dialog without the ref.
                    const panel = this.$refs.dialogPanel || this.$el;
                    this._trapEl = panel;
                    const focusable = Array.from(
                        panel.querySelectorAll(
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
                    panel.addEventListener("keydown", this._focusTrap);
                });
            },

            _closeDialog() {
                this.open = false;
                if (this._focusTrap) {
                    (this._trapEl || this.$el).removeEventListener(
                        "keydown",
                        this._focusTrap
                    );
                    this._focusTrap = null;
                    this._trapEl = null;
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

    // examRunnerForm — wraps the whole runner body on every page. It owns two
    // things:
    //   1. A live "answered" tally (answeredCount) shown in the top bar and the
    //      submit modal. Persisted answers on OTHER pages come from the server as
    //      data-answered-base; answers on the CURRENT page are counted live from
    //      the DOM and added on every input/change.
    //   2. The final-page review/submit confirmation dialog (built on the shared
    //      makeConfirmDialog focus-trap pattern). The dialog panel is only
    //      rendered on the final page, but the component wraps every page so the
    //      top-bar tally is live everywhere.
    //
    // Template wires:
    //   x-data="examRunnerForm"  data-answered-base="{N}"  on the runner wrapper
    //   x-text="answeredCount"   on the top-bar count and the modal count
    //   x-ref="pageForm"         on the <form> holding this page's questions
    //   x-on:click="openSubmitDialog"  on the final-page "Next" button
    //   x-on:click="closeSubmitDialog" on "Go back and review" / close
    //   x-on:keydown.escape.window="closeSubmitDialog"  on the dialog panel
    //   x-show="open"  x-cloak  on the dialog panel
    //   x-on:click="submit($refs.pageForm)"  x-bind:disabled="submitting"  on Submit
    Alpine.data("examRunnerForm", makeConfirmDialog({
        submitting: false,
        answeredCount: 0,
        _answeredBase: 0,
        _formEl: null,
        _recompute: null,
        _onPageShow: null,

        init() {
            const base = parseInt(this.$el.dataset.answeredBase || "0", 10);
            this._answeredBase = Number.isNaN(base) ? 0 : base;
            this._formEl = this.$refs.pageForm || null;
            this._recompute = () => {
                this.answeredCount = this._answeredBase + this._countAnsweredOnPage();
            };
            this._recompute();
            if (this._formEl) {
                this._formEl.addEventListener("input", this._recompute);
                this._formEl.addEventListener("change", this._recompute);
            }

            // Re-enable the Submit button if the page is restored from the
            // bfcache (e.g. back button), which does not re-run init().
            // Without this the button could come back disabled from a prior
            // submit attempt. Also clear the nav flag so the beforeunload
            // guard is armed again on the restored page.
            this._onPageShow = () => {
                this.submitting = false;
                runnerNavigating = false;
            };
            window.addEventListener("pageshow", this._onPageShow);
        },

        destroy() {
            if (this._formEl && this._recompute) {
                this._formEl.removeEventListener("input", this._recompute);
                this._formEl.removeEventListener("change", this._recompute);
            }
            if (this._onPageShow) {
                window.removeEventListener("pageshow", this._onPageShow);
                this._onPageShow = null;
            }
            this._closeDialog();
        },

        // Count questions on this page that have an answer. Inputs are grouped by
        // name (question_{id}) so a radio/checkbox option group counts once.
        _countAnsweredOnPage() {
            if (!this._formEl) return 0;
            const groups = {};
            this._formEl
                .querySelectorAll(
                    'input[name^="question_"], textarea[name^="question_"]'
                )
                .forEach((el) => {
                    (groups[el.name] ||= []).push(el);
                });
            let count = 0;
            Object.values(groups).forEach((els) => {
                const answered = els.some((el) => {
                    if (el.type === "radio" || el.type === "checkbox") {
                        return el.checked;
                    }
                    return el.value.trim() !== "";
                });
                if (answered) count += 1;
            });
            return count;
        },

        openSubmitDialog(triggerEl) {
            // Enforce required answers before opening the submit dialog, matching
            // the intermediate-page "Next" buttons (real type=submit, which the
            // browser validates). Validating here — while the form is still
            // visible — surfaces the browser's validation UI on the offending
            // field, instead of after the modal backdrop has covered it.
            // reportValidity() only blocks on fields marked `required`, so
            // optional/survey questions are unaffected.
            const form = this.$refs.pageForm;
            if (form && typeof form.reportValidity === "function" && !form.reportValidity()) {
                return;
            }
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
            // Deliberate submit — suppress the beforeunload "Leave site?" prompt.
            // form.submit() fires no submit event, so the examRunner capture
            // listener cannot catch this path; set the flag directly.
            runnerNavigating = true;
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
