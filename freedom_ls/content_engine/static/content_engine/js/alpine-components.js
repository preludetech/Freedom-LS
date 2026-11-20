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
 * - `audioClip`       — one audio element per clip, with seeking (cotton/audio-clip.html)
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
    // The one widget whose audio is playing or loading, as {id, pause}.
    // Starting any widget pauses this one first.
    let activeAudio = null;

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
                if (activeAudio && activeAudio.id !== this._id) activeAudio.pause();
                const id = this._id;
                activeAudio = {
                    id,
                    pause: () => {
                        // A later audioFile may already own the shared element; then
                        // this handle is stale and must not stop it.
                        if (owner?._id !== id) return;
                        sharedAudio.pause();
                        sharedAudio.currentTime = 0;
                        owner.failed = false;
                        owner._setState("idle");
                    },
                };
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
                if (activeAudio?.id === this._id) activeAudio = null;
            },
            _sounding() {
                return owner?._id === this._id && !this.idle;
            },
            destroy() {
                if (owner?._id === this._id) {
                    sharedAudio.pause();
                    owner = null;
                }
                if (activeAudio?.id === this._id) activeAudio = null;
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

    // How long a revealed answer stays up after its audio stops.
    const AUDIO_REVEAL_HIDE_DELAY_MS = 5000;

    Alpine.data("audioReveal", () => {
        const player = audioPlayer();
        return {
            ...player,
            revealed: false,
            _hideTimer: null,

            init() {
                // The countdown runs only while this widget is silent, so the
                // answer never hides mid-clip and a replay starts it over.
                this.$watch("idle", (idle) => {
                    this._clearHideTimer();
                    if (idle && this.revealed) {
                        this._hideTimer = setTimeout(() => this.hide(), AUDIO_REVEAL_HIDE_DELAY_MS);
                    }
                });
            },
            destroy() {
                this._clearHideTimer();
                player.destroy.call(this);
            },
            answerClass() {
                return { invisible: !this.revealed };
            },
            revealButtonClass() {
                return { invisible: this.revealed };
            },
            announcement() {
                return this.revealed ? this.$root.dataset.label : "";
            },
            reveal() {
                this.revealed = true;
                // Synchronous inside the click, so iOS lets it play.
                this._start(this.$root.dataset.src);
                // The reveal button turns inert, so focus moves to the answer.
                this.$nextTick(() => this.$refs.answer.querySelector("button")?.focus());
            },
            hide() {
                this._clearHideTimer();
                if (this._sounding()) this._stop();
                // The error line points at the play button, which hides now.
                this.failed = false;
                const focusWasInAnswer = this.$refs.answer.contains(document.activeElement);
                this.revealed = false;
                if (focusWasInAnswer) this.$nextTick(() => this.$refs.revealButton.focus());
            },
            _clearHideTimer() {
                clearTimeout(this._hideTimer);
                this._hideTimer = null;
            },
        };
    });

    // Audio clip component (cotton/audio-clip.html).
    //
    // Unlike audioFile, each clip owns its element so a long recording keeps
    // its position while another clip plays.
    let nextAudioClipId = 0;
    // Audio elements live outside Alpine's reactive data: a proxied media
    // element misbehaves, and each clip keeps its own so a paused clip keeps
    // its buffer.
    const clipElements = new Map();

    // m:ss under an hour, h:mm:ss from an hour up, chosen from the total; both
    // values floored so elapsed never reads past the total.
    function formatClipTime(seconds, total) {
        const whole = Math.floor(seconds);
        const pad = (n) => String(n).padStart(2, "0");
        if (total !== null && Math.floor(total) >= 3600) {
            const hours = Math.floor(whole / 3600);
            const minutes = Math.floor((whole % 3600) / 60);
            return `${hours}:${pad(minutes)}:${pad(whole % 60)}`;
        }
        return `${Math.floor(whole / 60)}:${pad(whole % 60)}`;
    }

    // "1 minute 12 seconds": floored, singular for 1, zero units left out, 0 is "0 seconds".
    function spokenDuration(seconds) {
        const whole = Math.floor(seconds);
        const units = [
            [Math.floor(whole / 3600), "hour"],
            [Math.floor((whole % 3600) / 60), "minute"],
            [whole % 60, "second"],
        ];
        const parts = units
            .filter(([value]) => value > 0)
            .map(([value, unit]) => `${value} ${unit}${value === 1 ? "" : "s"}`);
        return parts.length ? parts.join(" ") : "0 seconds";
    }

    Alpine.data("audioClip", () => ({
        _id: `clip-${nextAudioClipId++}`,
        state: "paused", // paused | loading | playing | failed
        elapsed: 0,
        duration: null, // the stored length until the element reports its own
        pendingSeek: null, // a seek made before the element had metadata
        dragging: false, // true between the first input and the change of a drag
        transcriptOpen: false,

        init() {
            const stored = parseFloat(this.$el.dataset.duration);
            this.duration = Number.isFinite(stored) ? stored : null;
        },
        get playing() {
            return this.state === "playing";
        },
        get loading() {
            return this.state === "loading";
        },
        get failed() {
            return this.state === "failed";
        },
        get elapsedText() {
            return formatClipTime(this.elapsed, this.duration);
        },
        get totalText() {
            return this.duration === null ? "--:--" : formatClipTime(this.duration, this.duration);
        },
        get transcriptToggleText() {
            return this.transcriptOpen ? "Hide transcript" : "Show transcript";
        },
        toggleTranscript() {
            this.transcriptOpen = !this.transcriptOpen;
        },
        get statusText() {
            return this.failed ? "This audio couldn't load." : "";
        },
        get showPlayIcon() {
            return this.state === "paused" || this.state === "failed";
        },
        get seekMax() {
            return this.duration ?? 0;
        },
        get seekDisabled() {
            return this.duration === null;
        },
        // floor() makes this change at most once a second during playback
        get valueText() {
            const elapsed = spokenDuration(this.elapsed);
            return this.duration === null ? elapsed : `${elapsed} of ${spokenDuration(this.duration)}`;
        },
        get playedStyle() {
            return { "--played": `${this.duration ? (this.elapsed / this.duration) * 100 : 0}%` };
        },

        seekInput(event) {
            this.dragging = true;
            this.elapsed = Number(event.target.value);
        },
        seekChange(event) {
            this.dragging = false;
            this._seekTo(Number(event.target.value));
        },
        seekKey(event) {
            // step="any" leaves the browser's arrow step undefined, so arrows are handled here.
            const delta = { ArrowLeft: -5, ArrowRight: 5 }[event.key];
            if (delta === undefined || this.seekDisabled) return;
            event.preventDefault();
            this._seekTo(Math.min(Math.max(this.elapsed + delta, 0), this.seekMax));
        },
        _seekTo(seconds) {
            this.elapsed = seconds;
            const audio = clipElements.get(this._id);
            if (!audio || audio.readyState < HTMLMediaElement.HAVE_METADATA) {
                this.pendingSeek = seconds;
                return;
            }
            // No play() here, so a paused clip stays paused.
            audio.currentTime = seconds;
        },

        toggle() {
            if (this.state === "playing" || this.state === "loading") {
                this._element().pause();
                return;
            }
            this._start(this._element());
        },
        _element() {
            let audio = clipElements.get(this._id);
            if (audio) return audio;
            audio = new Audio();
            audio.preload = "none";
            audio.src = this._src;
            audio.addEventListener("playing", () => { this.state = "playing"; });
            audio.addEventListener("waiting", () => { if (!audio.paused) this.state = "loading"; });
            audio.addEventListener("pause", () => { if (this.state !== "failed") this.state = "paused"; });
            // Assigning src resets currentTime to 0; while a seek is pending or
            // being dragged the saved position must not be overwritten.
            audio.addEventListener("timeupdate", () => {
                if (!this.dragging && this.pendingSeek === null) this.elapsed = audio.currentTime;
            });
            audio.addEventListener("loadedmetadata", () => {
                // The stored length is an estimate for some VBR files; the element's own is exact.
                if (Number.isFinite(audio.duration)) this.duration = audio.duration;
                if (this.pendingSeek !== null) {
                    audio.currentTime = this.pendingSeek;
                    this.pendingSeek = null;
                }
                // A max that grew from 0 leaves the browser's clamped value behind.
                this.$refs.seek.value = this.elapsed;
            });
            audio.addEventListener("ended", () => {
                audio.currentTime = 0;
                this.elapsed = 0;
                this.state = "paused";
            });
            audio.addEventListener("error", () => this._fail());
            clipElements.set(this._id, audio);
            return audio;
        },
        // The redirect URL, never a signed one, so a page left open past the signature still plays.
        get _src() {
            return this.$refs.play.dataset.src;
        },
        _start(audio) {
            if (activeAudio && activeAudio.id !== this._id) activeAudio.pause();
            activeAudio = { id: this._id, pause: () => audio.pause() };
            this.state = "loading";
            // Called synchronously inside the click so iOS treats it as user-initiated.
            audio.play().catch((error) => {
                if (error.name !== "AbortError") this._fail();
            });
        },
        _fail() {
            this.state = "failed";
        },
        retry() {
            const audio = this._element();
            // Keep the position across the fresh load.
            this.pendingSeek = this.elapsed;
            // Setting src again goes back through the redirect for a freshly signed URL.
            audio.src = this._src;
            this._start(audio);
        },
        destroy() {
            const audio = clipElements.get(this._id);
            if (audio) {
                audio.pause();
                audio.removeAttribute("src");
                audio.load();
                clipElements.delete(this._id);
            }
            if (activeAudio?.id === this._id) activeAudio = null;
        },
    }));
});
