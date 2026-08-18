/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { useDebounced } from "@web/core/utils/timing";

/**
 * Lightweight autocomplete used by the many2one / many2many column filters.
 * It reuses the server-side `name_search` (the same call the native relational
 * widgets use) and keeps a list of picked records ({id, display_name}).
 *
 * Props:
 *   - relation: string, the co-model to search
 *   - value: Array<{id, display_name}>, currently picked records (reactive)
 *   - update: (records) => void, called with the new picked list
 */
export class Many2XFilterInput extends Component {
    static template = "sp_list_view_advanced_search.Many2XFilterInput";
    static props = {
        relation: String,
        value: { type: Array },
        update: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ query: "", results: [], open: false });
        this.search = useDebounced(this._search.bind(this), 250);
    }

    async _search() {
        const term = this.state.query.trim();
        const excludeIds = this.props.value.map((r) => r.id);
        const pairs = await this.orm.call(this.props.relation, "name_search", [], {
            name: term,
            // v17/v18 name_search uses the `args` kwarg (renamed to `domain` in v19).
            args: excludeIds.length ? [["id", "not in", excludeIds]] : [],
            limit: 8,
        });
        this.state.results = pairs.map(([id, display_name]) => ({ id, display_name }));
        this.state.open = true;
    }

    onInput(ev) {
        this.state.query = ev.target.value;
        this.search();
    }

    onFocus() {
        if (!this.state.results.length) {
            this._search();
        } else {
            this.state.open = true;
        }
    }

    pick(record) {
        this.props.update([...this.props.value, record]);
        this.state.query = "";
        this.state.results = [];
        this.state.open = false;
    }

    remove(record) {
        this.props.update(this.props.value.filter((r) => r.id !== record.id));
    }

    onBlur() {
        // Delay so a click on a result registers before the list closes.
        setTimeout(() => (this.state.open = false), 150);
    }
}
