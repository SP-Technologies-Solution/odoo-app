/** @odoo-module **/

import { reactive } from "@odoo/owl";
import { buildFieldDomain, describeConditions } from "./utils/domain_builder";

/**
 * One manager instance per ListRenderer. It owns the reactive source of truth
 * for the active per-column filters and mirrors them into the view's
 * SearchModel as ordinary removable facets — so the rest of Odoo (pager,
 * record count, facet chips, export) treats them like any native filter.
 *
 * State shape:
 *   filters[fieldName] = {
 *       kind,            // widget kind ("text" | "numeric" | ...)
 *       label,           // column label, used for the facet text
 *       conditions,      // array of condition objects
 *       groupId,         // search-model group id of the facet we created
 *   }
 */
export class ColumnFilterManager {
    constructor(searchModel) {
        this.searchModel = searchModel;
        this.state = reactive({ filters: {} });
        // Guards reconcile() from firing while we mutate the search model.
        this._syncing = false;
    }

    hasFilter(fieldName) {
        const entry = this.state.filters[fieldName];
        return Boolean(entry && entry.conditions.length);
    }

    getEntry(fieldName) {
        return this.state.filters[fieldName];
    }

    /**
     * Replace the conditions for a column and push the result to the search
     * model. Passing an empty condition list clears the column.
     */
    apply(fieldName, { kind, label, conditions, field }) {
        const active = conditions.filter(Boolean);
        const prev = this.state.filters[fieldName];
        const prevGroupId = prev && prev.groupId;

        this._syncing = true;
        try {
            if (prevGroupId !== undefined) {
                this.searchModel.deactivateGroup(prevGroupId);
            }
            const domain = buildFieldDomain(kind, fieldName, active);
            if (domain.length) {
                const groupId = this.searchModel.nextGroupId;
                this.searchModel.createNewFilters([
                    {
                        description: describeConditions(kind, label, active, field),
                        domain,
                    },
                ]);
                this.state.filters[fieldName] = {
                    kind,
                    label,
                    field,
                    conditions: active,
                    groupId,
                };
            } else {
                delete this.state.filters[fieldName];
            }
        } finally {
            this._syncing = false;
        }
    }

    clear(fieldName) {
        this.apply(fieldName, {
            kind: (this.state.filters[fieldName] || {}).kind,
            label: (this.state.filters[fieldName] || {}).label,
            conditions: [],
            field: (this.state.filters[fieldName] || {}).field,
        });
    }

    /**
     * Called on every SearchModel "update". If a facet we created was removed
     * from the search bar directly by the user, drop it from our state so the
     * column's badge clears and the popover reopens empty.
     */
    reconcile() {
        if (this._syncing) {
            return;
        }
        const liveGroupIds = new Set(this.searchModel.facets.map((f) => f.groupId));
        for (const [fieldName, entry] of Object.entries(this.state.filters)) {
            if (entry.groupId !== undefined && !liveGroupIds.has(entry.groupId)) {
                delete this.state.filters[fieldName];
            }
        }
    }
}
