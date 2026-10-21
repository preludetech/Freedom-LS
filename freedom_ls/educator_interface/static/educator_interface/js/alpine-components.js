document.addEventListener("alpine:init", () => {
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
            window.dispatchEvent(new CustomEvent("member-role-chosen"));
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
});
