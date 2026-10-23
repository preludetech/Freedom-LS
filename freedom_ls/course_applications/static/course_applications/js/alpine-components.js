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
});
