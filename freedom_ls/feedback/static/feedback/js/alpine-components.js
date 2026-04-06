/**
 * Feedback Alpine.js components (CSP-compatible).
 * Loaded via extra_alpine_components block in _base.html.
 */
document.addEventListener("alpine:init", () => {
    Alpine.data("starRating", () => ({
        rating: 0,
        hoverRating: 0,
        setRating(value) {
            this.rating = value;
        },
        setHover(value) {
            this.hoverRating = value;
        },
        clearHover() {
            this.hoverRating = 0;
        },
        _starClass(index) {
            return (this.hoverRating || this.rating) >= index ? "text-warning" : "text-muted";
        },
        star1Class() { return this._starClass(1); },
        star2Class() { return this._starClass(2); },
        star3Class() { return this._starClass(3); },
        star4Class() { return this._starClass(4); },
        star5Class() { return this._starClass(5); },
    }));

    Alpine.data("feedbackThankYou", () => ({
        init() {
            this.$dispatch("feedback-submitted");
        },
    }));

    Alpine.data("feedbackModal", () => ({
        open: false,
        formId: null,
        contentTypeId: null,
        objectId: null,
        submitted: false,
        _handler: null,
        _feedbackHandler: null,
        init() {
            // Listen for HX-Trigger event from HTMX partial responses
            this._handler = (event) => {
                const data = event.detail;
                if (data) {
                    this.formId = data.form_id;
                    this.contentTypeId = data.content_type_id;
                    this.objectId = data.object_id;
                    this.loadForm();
                }
            };
            document.body.addEventListener("show-feedback-modal", this._handler);

            // Listen for feedback submission from child component
            this._feedbackHandler = () => {
                this.onSubmitted();
            };
            this.$el.addEventListener("feedback-submitted", this._feedbackHandler);

            // Check if we should auto-load (data attributes set by server)
            if (this.$el.dataset.autoLoad === "true") {
                this.formId = this.$el.dataset.formId;
                this.contentTypeId = this.$el.dataset.contentTypeId;
                this.objectId = this.$el.dataset.objectId;
                this.loadForm();
            }
        },
        destroy() {
            if (this._handler) {
                document.body.removeEventListener("show-feedback-modal", this._handler);
            }
            if (this._feedbackHandler) {
                this.$el.removeEventListener("feedback-submitted", this._feedbackHandler);
            }
        },
        _baseUrl() {
            return this.$el.dataset.baseUrl || "/feedback";
        },
        loadForm() {
            this.open = true;
            // Trigger HTMX request to load the form into the modal content area
            const target = this.$el.querySelector("[data-feedback-content]");
            if (target && this.formId) {
                const url = this._baseUrl() + "/form/" + this.formId + "/?content_type_id=" + this.contentTypeId + "&object_id=" + this.objectId;
                htmx.ajax("GET", url, { target: target, swap: "innerHTML", source: this.$el });
            }
        },
        close() {
            if (!this.submitted && this.formId) {
                const url = this._baseUrl() + "/dismiss/" + this.formId + "/";
                htmx.ajax("POST", url, {
                    source: this.$el,
                    values: {
                        content_type_id: this.contentTypeId,
                        object_id: this.objectId,
                    },
                });
            }
            this.open = false;
        },
        onEscape() {
            this.close();
        },
        onSubmitted() {
            this.submitted = true;
            setTimeout(() => {
                this.open = false;
            }, 2000);
        },
    }));
});
