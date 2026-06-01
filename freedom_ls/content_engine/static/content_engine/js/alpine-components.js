/**
 * Alpine.js CSP-compatible component registrations for content widgets.
 *
 * The @alpinejs/csp build does not support inline JS expressions.
 * All Alpine components must be registered via Alpine.data().
 * Load this script BEFORE the Alpine CSP script.
 *
 * Components here back the cotton content widgets rendered inside markdown
 * (e.g. equations and lightboxes). Later tasks add `equation` and
 * `contentLightbox` registrations into the alpine:init block below.
 */

document.addEventListener("alpine:init", () => {
    // Equation component (cotton/equation.html).
    //
    // Typesets the LaTeX source held in the `src` ref using the vendored
    // KaTeX library and swaps it for the rendered output. Rendering is
    // widget-scoped (only c-equation containers) so prose currency like
    // "$5" is never touched. The source is read via textContent (decoded
    // characters, not innerHTML) so KaTeX receives the real LaTeX.
    //
    // Failure modes degrade gracefully: throwOnError:false leaves malformed
    // LaTeX as readable source, and a missing/late KaTeX global leaves the
    // raw source visible rather than throwing.
    Alpine.data("equation", () => ({
        init() {
            if (!window.katex || !this.$refs.src || !this.$refs.out) return;
            const source = this.$refs.src.textContent;
            try {
                window.katex.render(source, this.$refs.out, {
                    displayMode: true,
                    throwOnError: false, // malformed LaTeX degrades to source
                    trust: false, // SECURITY: block \href \url \includegraphics
                    strict: "ignore",
                    output: "htmlAndMathml", // MathML for screen readers
                });
                this.$refs.src.hidden = true;
                this.$refs.out.hidden = false;
            } catch (e) {
                // Leave the raw LaTeX source visible as the fallback.
            }
        },
    }));

    // Content lightbox component (cotton/picture.html).
    //
    // Focus-managing modal for image thumbnails. On open it remembers the
    // triggering element and moves focus to the close button; on close it
    // restores focus to the trigger (so keyboard users return to where they
    // were). Escape closes. This lives in content_engine (not base) so the
    // content widgets own their interactive behaviour.
    Alpine.data("contentLightbox", () => ({
        open: false,
        _trigger: null,
        show() {
            // Capture the trigger explicitly (the x-ref), not document
            // .activeElement: some browsers don't focus a <button> on mouse
            // click, which would lose the restore target on close.
            this._trigger = this.$refs.trigger || document.activeElement;
            this.open = true;
            this.$nextTick(() => {
                if (this.$refs.closeBtn) this.$refs.closeBtn.focus();
            });
        },
        close() {
            this.open = false;
            if (this._trigger) this._trigger.focus();
        },
        onEscape() {
            if (this.open) this.close();
        },
        // The dialog's only focusable target is the close button, so keep
        // focus on it (a minimal focus trap honouring aria-modal="true").
        onTab() {
            if (this.open && this.$refs.closeBtn) this.$refs.closeBtn.focus();
        },
    }));
});
