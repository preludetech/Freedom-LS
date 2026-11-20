/**
 * Alpine.js CSP-compatible component registrations for course_applications.
 * Load this script BEFORE the Alpine CSP script.
 */

document.addEventListener("alpine:init", () => {
    // Claim link notice (partials/claim_link_notice.html). Change reveals the
    // change-address form in place. The notice the server swaps back in after
    // a failed change carries data-editing="true", so the form opens again on
    // its error with the field focused.
    Alpine.data("claimLinkNotice", () => ({
        editing: false,
        init() {
            if (this.$el.dataset.editing === "true") {
                this.editing = true;
                this.focusEmail();
            }
        },
        toggleEditing() {
            this.editing = !this.editing;
            if (this.editing) this.focusEmail();
        },
        focusEmail() {
            // x-show reveals the form on the next tick; a hidden input cannot
            // take focus.
            this.$nextTick(() => this.$refs.emailInput.focus());
        },
    }));

    // Withdraw confirmation (application_status.html). The trigger is a submit
    // button, so with no JavaScript it posts the form straight away; here the
    // click opens the dialog instead and Withdraw submits the form. Focus
    // moves into the dialog, Tab stays inside it, and closing returns focus to
    // the trigger. course_applications cannot import learner_interface's
    // confirm dialog, so the behaviour is repeated.
    Alpine.data("withdrawDialog", () => ({
        open: false,
        _triggerEl: null,
        _panelEl: null,
        _focusTrap: null,
        confirmWithdraw(event) {
            event.preventDefault();
            this._triggerEl = event.currentTarget;
            this.open = true;
            this.$nextTick(() => {
                const panel = this.$refs.dialogPanel;
                this._panelEl = panel;
                const focusable = Array.from(
                    panel.querySelectorAll("button, [href], input, select, textarea")
                );
                focusable[0].focus();
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
        dismiss() {
            if (!this.open) return;
            this._closeDialog();
        },
        withdraw() {
            this.$refs.withdrawForm.submit();
        },
        _closeDialog() {
            this.open = false;
            if (this._focusTrap) {
                this._panelEl.removeEventListener("keydown", this._focusTrap);
                this._focusTrap = null;
                this._panelEl = null;
            }
            if (this._triggerEl) {
                this._triggerEl.focus();
                this._triggerEl = null;
            }
        },
        destroy() {
            this._closeDialog();
        },
    }));
});
