import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { makeAwaitable } from "@point_of_sale/app/store/make_awaitable_dialog";
import { SpMergeOrdersPopup } from "@sp_pos_merge_table_orders/app/store/merge_orders_popup/merge_orders_popup";

patch(ControlButtons.prototype, {
    /**
     * Show the button only when merging is enabled, the current order sits on a
     * table, and at least one other mergeable order exists on the same floor.
     */
    get spShowMergeOrders() {
        const order = this.currentOrder;
        if (!this.pos.config.sp_merge_orders_enabled || !order || !order.table_id) {
            return false;
        }
        return this.pos.spMergeCandidates(order).length > 0;
    },

    async clickMergeOrders() {
        const order = this.currentOrder;
        const candidates = this.pos.spMergeCandidates(order);
        if (!candidates.length) {
            this.notification.add(_t("There is no other order to merge on this floor."), {
                type: "warning",
            });
            return;
        }
        const selected = await makeAwaitable(this.dialog, SpMergeOrdersPopup, {
            title: _t("Merge Orders"),
            orders: candidates,
        });
        if (!selected || !selected.length) {
            return;
        }
        const merged = await this.pos.spMergeSelectedOrders(order, selected);
        if (merged.length) {
            this.notification.add(
                _t("Merged %s order(s) into this one.", merged.length),
                { type: "success" }
            );
        }
    },
});
