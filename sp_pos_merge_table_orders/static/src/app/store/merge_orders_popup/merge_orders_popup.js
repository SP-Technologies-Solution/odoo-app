import { _t } from "@web/core/l10n/translation";
import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

/**
 * Multi-select dialog listing the open orders that can be merged into the
 * current order. Returns the selected order objects through ``getPayload``
 * (see makeAwaitable), or nothing when cancelled.
 */
export class SpMergeOrdersPopup extends Component {
    static template = "sp_pos_merge_table_orders.SpMergeOrdersPopup";
    static components = { Dialog };
    static props = {
        title: { type: String, optional: true },
        orders: { type: Array },
        getPayload: Function,
        close: Function,
    };
    static defaultProps = {
        title: _t("Merge Orders"),
    };

    setup() {
        this.state = useState({ selected: new Set() });
    }

    isSelected(order) {
        return this.state.selected.has(order.uuid);
    }

    toggle(order) {
        if (this.state.selected.has(order.uuid)) {
            this.state.selected.delete(order.uuid);
        } else {
            this.state.selected.add(order.uuid);
        }
    }

    tableLabel(order) {
        return order.table_id ? order.table_id.getName() : _t("No table");
    }

    lineCount(order) {
        return order.lines.length;
    }

    total(order) {
        return this.env.utils.formatCurrency(order.get_total_with_tax());
    }

    get canConfirm() {
        return this.state.selected.size > 0;
    }

    confirm() {
        const chosen = this.props.orders.filter((order) =>
            this.state.selected.has(order.uuid)
        );
        this.props.getPayload(chosen);
        this.props.close();
    }
}
