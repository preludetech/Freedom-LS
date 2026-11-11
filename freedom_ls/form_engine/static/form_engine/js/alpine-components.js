/**
 * Alpine components for form_engine.
 *
 * CSP build: every component is registered with Alpine.data() and directives
 * reference method or property names only — zero inline expressions.
 */
document.addEventListener("alpine:init", () => {
    /**
     * Refuses an oversized file in the browser rather than uploading it and
     * being told no. htmx:confirm fires on the element before the request goes
     * out and honours preventDefault(), so the file never leaves the machine.
     * The server still enforces the same cap; this only saves the round trip.
     */
    Alpine.data("questionFileUpload", () => ({
        oversized: false,

        checkSize(event) {
            const input = event.target;
            const file = input.files && input.files[0];
            // $root, not $el: this runs from the input's own x-on, where $el
            // is the input. The limit is on the widget root.
            const max = Number(this.$root.dataset.maxBytes);
            this.oversized = Boolean(file && file.size > max);
            if (this.oversized) {
                event.preventDefault();
                input.value = "";
            }
        },
    }));

    /**
     * Keeps the phone question's example hint on the chosen country. The
     * server renders the hint for the country it selected, so this only
     * follows later changes to the picker.
     */
    Alpine.data("phoneHint", () => ({
        examples: {},
        example: "",

        init() {
            const data = document.getElementById(this.$root.dataset.examplesId);
            this.examples = JSON.parse(data.textContent);
            this.example = this.$root.dataset.example;
        },

        pickCountry(event) {
            this.example = this.examples[event.target.value] || "";
        },

        hasExample() {
            return this.example !== "";
        },
    }));
});
