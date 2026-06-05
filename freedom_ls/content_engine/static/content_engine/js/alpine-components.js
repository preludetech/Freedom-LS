/**
 * Alpine.js CSP-compatible component registrations for content widgets.
 *
 * The @alpinejs/csp build does not support inline JS expressions.
 * All Alpine components must be registered via Alpine.data().
 * Load this script BEFORE the Alpine CSP script.
 *
 * Components here back the cotton content widgets rendered inside markdown:
 * - `equation`        — client-side KaTeX typesetting (cotton/equation.html)
 * - `contentLightbox` — native <dialog> spotlight (cotton/picture.html)
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

    // Content lightbox — native <dialog> spotlight (cotton/picture.html).
    // showModal() provides focus-trap, Escape, inert background and focus-restore
    // to the trigger; we only add open() and a backdrop-click-to-close guard.
    Alpine.data("contentLightbox", () => ({
        open() {
            this.$refs.dialog.showModal();
        },
        close() {
            this.$refs.dialog.close();
        },
        onBackdropClick(event) {
            // The full-viewport dialog reports event.target === the dialog only
            // when the surrounding scrim is clicked; the card/image are
            // descendants and are correctly ignored. Mirrors sidePanel.
            if (event.target === this.$refs.dialog) this.close();
        },
    }));
});
