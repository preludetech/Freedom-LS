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

    // The cohort checklist of the Add member dialog. A row shows when its
    // name contains the search text and the chosen role is one of the roles
    // the row is offered for (data-roles). A row that is not offered is also
    // disabled, so it is neither counted nor submitted.
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
            const checked = this.$root
                .closest("form")
                .querySelector('input[name="role"]:checked');
            return checked === null ? "" : checked.value;
        },

        filter() {
            const role = this._chosenRole();
            const text = this.query.trim().toLowerCase();
            this.$root.querySelectorAll("[data-cohort-row]").forEach((row) => {
                const offered = row.dataset.roles.split(" ").includes(role);
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
