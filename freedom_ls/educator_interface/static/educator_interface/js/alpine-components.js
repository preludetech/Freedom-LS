document.addEventListener("alpine:init", () => {
    // The course outline table. A group row (a part, a multi-page form)
    // toggles its child rows, and a child row hides with any group above
    // it. Every group is open by default and never remembered: an educator
    // reads the whole outline, so there is no state worth keeping.
    // The CSP build passes no arguments, so a toggle names its row and a
    // child row its groups through data attributes.
    Alpine.data("courseOutline", () => ({
        collapsed: {},
        toggle(event) {
            const rowId = event.currentTarget.dataset.row;
            this.collapsed[rowId] = !this.collapsed[rowId];
        },
        expandedAttr() {
            return this.collapsed[this.$el.dataset.row] ? "false" : "true";
        },
        shown() {
            const parents = (this.$el.dataset.parents || "").split(" ");
            return parents.every((rowId) => !this.collapsed[rowId]);
        },
    }));

    // The role radios of the Add member dialog. The cohorts block shows only
    // for a role that is given on cohorts, which each radio announces with
    // its data-needs-cohorts attribute. Choosing a role tells the checklist,
    // which offers only the cohorts that role may be given on.
    Alpine.data("memberRoleChooser", () => ({
        showsCohorts: false,

        init() {
            this.syncRole();
        },

        syncRole() {
            const checked = this.$root.querySelector('input[name="role"]:checked');
            this.showsCohorts = checked !== null && checked.dataset.needsCohorts === "true";
        },

        chooseRole() {
            this.syncRole();
            window.dispatchEvent(new CustomEvent("staff-role-chosen"));
        },
    }));

    // A cohort checklist. A row shows when its name contains the search text
    // and, in a form with role radios, the chosen role is one of the roles the
    // row is offered for (data-roles). A row that is not offered is also
    // disabled, so it is neither counted nor submitted. In a form with no role
    // radios every row is offered.
    Alpine.data("cohortChecklist", () => ({
        query: "",
        selected: 0,

        get selectedLabel() {
            return this.selected + " selected";
        },

        init() {
            this.filter();
        },

        _chosenRole() {
            const form = this.$root.closest("form");
            if (form.querySelector('input[type="radio"][name="role"]') === null) {
                return null;
            }
            const checked = form.querySelector('input[name="role"]:checked');
            return checked === null ? "" : checked.value;
        },

        filter() {
            const role = this._chosenRole();
            const text = this.query.trim().toLowerCase();
            this.$root.querySelectorAll("[data-cohort-row]").forEach((row) => {
                const offered = role === null || row.dataset.roles.split(" ").includes(role);
                row.querySelector("input").disabled = !offered;
                row.hidden = !offered || !row.dataset.name.includes(text);
            });
            this.count();
        },

        count() {
            this.selected = this.$root.querySelectorAll(
                "[data-cohort-row] input:checked:not(:disabled)",
            ).length;
        },
    }));

    // The email field of the Add staff member dialog as a list-autocomplete
    // combobox. The server swaps in the matching people as role="option"
    // rows; the arrow keys move through them, Enter or a click copies the
    // option's data-email into the posted email field and submits the lookup,
    // and Escape closes the list without closing the dialog (the native
    // dialog closes on Escape unless its default action is prevented). The visible
    // input is the search term (q); the hidden email input is what posts.
    Alpine.data("staffSearchCombobox", () => ({
        expanded: false,
        activeIndex: -1,

        get activeId() {
            const active = this.options()[this.activeIndex];
            return active === undefined ? null : active.id;
        },

        options() {
            return Array.from(
                this.$root.querySelectorAll('[role="option"]:not([aria-disabled])'),
            );
        },

        syncEmail(event) {
            this.$root.querySelector('input[name="email"]').value = event.target.value;
        },

        markActive() {
            this.options().forEach((option, index) => {
                if (index === this.activeIndex) {
                    option.setAttribute("aria-selected", "true");
                    option.scrollIntoView({ block: "nearest" });
                } else {
                    option.removeAttribute("aria-selected");
                }
            });
        },

        onKeydown(event) {
            const count = this.options().length;
            const pressed = event.key;
            if (pressed === "ArrowDown" || pressed === "ArrowUp") {
                if (count === 0) {
                    return;
                }
                event.preventDefault();
                this.expanded = true;
                const step = pressed === "ArrowDown" ? 1 : -1;
                this.activeIndex = (this.activeIndex + step + count) % count;
                this.markActive();
            } else if (pressed === "Enter") {
                const active = this.options()[this.activeIndex];
                if (this.expanded && active !== undefined) {
                    event.preventDefault();
                    this.choose(active);
                }
            } else if (pressed === "Escape" && this.expanded) {
                event.preventDefault();
                event.stopPropagation();
                this.close();
            }
        },

        pick(event) {
            this.choose(event.currentTarget);
        },

        choose(option) {
            const email = option.dataset.email;
            this.$root.querySelector('input[name="q"]').value = email;
            this.$root.querySelector('input[name="email"]').value = email;
            this.close();
            this.$root.closest("form").requestSubmit();
        },

        close() {
            this.expanded = false;
            this.activeIndex = -1;
            this.markActive();
        },

        setStatus(text) {
            this.$refs.status.textContent = text;
        },

        beforeRequest(event) {
            if (event.target.getAttribute("name") === "q") {
                this.setStatus("Searching…");
            }
        },

        afterSwap(event) {
            const results = this.$root.querySelector("#staff-search-results");
            if (event.target !== results) {
                return;
            }
            const count = parseInt(results.dataset.count, 10);
            this.activeIndex = -1;
            this.expanded = count > 0;
            if (results.dataset.state === "prompt") {
                this.setStatus("");
            } else if (count === 0) {
                this.setStatus("No results");
            } else {
                this.setStatus(count + (count === 1 ? " person found" : " people found"));
            }
        },
    }));
});
