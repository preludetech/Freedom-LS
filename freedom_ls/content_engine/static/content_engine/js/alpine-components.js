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
 * - `flashcard`       — two-sided flip card (cotton/flashcard.html)
 * - `audioFile`       — one shared audio element for speak buttons (cotton/audio.html)
 * - `audioReveal`     — say it, then reveal (cotton/audio-reveal.html)
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

    // Flashcard component (cotton/flashcard.html).
    //
    // Manages the flip state for the two-sided card widget. `flipped` tracks
    // which face is showing; `flip()` toggles it. `frontStyle()` and
    // `backStyle()` return style objects (not class strings) so the 3-D
    // rotation transforms are applied via x-bind:style, bypassing Tailwind
    // purging entirely.
    //
    // The transition between faces is gated behind the `motion-safe:` variant
    // on the face markup, so the state change (flip) always happens; only the
    // animation is dropped for users who prefer reduced motion.
    Alpine.data("flashcard", () => ({
        flipped: false,
        flip() { this.flipped = !this.flipped; },
        frontStyle() { return { transform: this.flipped ? "rotateY(180deg)" : "rotateY(0deg)" }; },
        backStyle()  { return { transform: this.flipped ? "rotateY(0deg)" : "rotateY(180deg)" }; },
    }));

    // Content lightbox — native <dialog> spotlight (cotton/picture.html).
    // showModal() provides focus-trap, Escape, inert background and focus-restore
    // to the trigger; we add open(), a backdrop-click-to-close guard, and a
    // background scroll-lock (showModal() makes the background inert but does
    // NOT stop it scrolling).
    Alpine.data("contentLightbox", () => ({
        init() {
            // Unlock on *every* close route — close button, Escape, scrim — by
            // listening to the dialog's native "close" event rather than only
            // our close() method (Escape never calls close()).
            this.$refs.dialog.addEventListener("close", () => this._unlockScroll());
        },
        open() {
            this._lockScroll();
            this.$refs.dialog.showModal();
        },
        close() {
            // Scroll is unlocked by the "close" event listener wired in init().
            this.$refs.dialog.close();
        },
        onBackdropClick(event) {
            // The full-viewport dialog reports event.target === the dialog only
            // when the surrounding scrim is clicked; the card/image are
            // descendants and are correctly ignored. Mirrors sidePanel.
            if (event.target === this.$refs.dialog) this.close();
        },
        _lockScroll() {
            // Stash the inline value so we restore exactly what was there (which
            // may be ""), not a hard-coded default.
            this._prevOverflow = document.documentElement.style.overflow;
            document.documentElement.style.overflow = "hidden";
        },
        _unlockScroll() {
            document.documentElement.style.overflow = this._prevOverflow ?? "";
        },
    }));

    // Audio file component (cotton/audio.html).
    //
    // One element for the whole page: it plays one audio file at a time by
    // construction, and iOS unlocks it once from the first press. Web Audio is
    // not used because the iPhone silent switch mutes it.
    let sharedAudio = null;
    let owner = null;
    // Alpine hands each method a fresh scope proxy, so `this` is not a stable
    // identity; widgets are compared by this id instead.
    let nextAudioFileId = 0;

    function audioElement() {
        if (sharedAudio) return sharedAudio;
        sharedAudio = new Audio();
        // Only a widget that is loading can start playing; a late event from
        // a load that was stopped does not restart the stop icon.
        sharedAudio.addEventListener("playing", () => {
            if (owner?.loading) owner._setState("playing");
        });
        sharedAudio.addEventListener("ended", () => owner?._setState("idle"));
        sharedAudio.addEventListener("pause", () => {
            // A src change can fire pause for the previous file after ownership
            // has moved; it is not a stop.
            if (owner && !owner.loading) owner._setState("idle");
        });
        // A failed load or play attempt; the button stays enabled so the next
        // press retries. A load the learner already stopped is not a failure.
        sharedAudio.addEventListener("error", () => {
            if (owner && !owner.idle) owner._fail();
        });
        return sharedAudio;
    }

    // The player half of an audio widget: its state, and taking or giving up
    // the page's one audio element. Each widget gets a fresh copy, so the owner
    // hand-off exists once and one file plays at a time across every widget.
    function audioPlayer() {
        return {
            _id: nextAudioFileId++,
            idle: true,
            loading: false,
            playing: false,
            failed: false,

            toggle() {
                if (this._sounding()) this._stop();
                else this._start(this.$el.dataset.src);
            },
            errorText() {
                return this.failed ? "Audio could not be played. Try again." : "";
            },
            // Takes the element from whoever owns it and plays from the start.
            // Never stops, so a second call while playing restarts the clip.
            _start(src) {
                const audio = audioElement();
                if (owner) {
                    owner.failed = false;
                    owner._setState("idle");
                }
                this.failed = false;
                owner = this;
                this._setState("loading");
                if (audio.getAttribute("src") === src && !audio.error) {
                    // The file is already loaded: replay it rather than fetch a
                    // freshly signed copy through the redirect.
                    audio.currentTime = 0;
                } else {
                    // src only, never <source type>: the stored mime type can be empty.
                    audio.src = src;
                }
                // Called synchronously inside the click so iOS treats it as user-initiated.
                audio.play().catch((error) => {
                    // AbortError means another press replaced this load; not a failure.
                    if (error.name !== "AbortError" && owner?._id === this._id) this._fail();
                });
            },
            _stop() {
                const audio = audioElement();
                audio.pause();
                audio.currentTime = 0;
                this._setState("idle");
            },
            _sounding() {
                return owner?._id === this._id && !this.idle;
            },
            destroy() {
                if (owner?._id === this._id) {
                    sharedAudio.pause();
                    owner = null;
                }
            },
            _fail() {
                this.failed = true;
                this._setState("idle");
            },
            _setState(state) {
                this.idle = state === "idle";
                this.loading = state === "loading";
                this.playing = state === "playing";
            },
        };
    }

    Alpine.data("audioFile", audioPlayer);

    Alpine.data("audioReveal", () => ({
        ...audioPlayer(),
        revealed: false,

        answerClass() {
            return { invisible: !this.revealed };
        },
        revealLabelClass() {
            return { invisible: this.revealed };
        },
        hideLabelClass() {
            return { invisible: !this.revealed };
        },
        announcement() {
            return this.revealed ? this.$root.dataset.label : "";
        },
        toggleReveal() {
            if (this.revealed) {
                if (this._sounding()) this._stop();
                this.revealed = false;
                return;
            }
            this.revealed = true;
            // Synchronous inside the click, so iOS lets it play.
            this._start(this.$root.dataset.src);
        },
    }));

});
