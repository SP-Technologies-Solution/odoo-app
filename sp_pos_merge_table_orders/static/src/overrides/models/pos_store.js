import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { _t } from "@web/core/l10n/translation";

patch(PosStore.prototype, {
    /**
     * True when a table currently holds at least one open, unpaid, non-empty
     * order that could be merged into another order. Drives the floor-plan
     * badge. Cheap enough to call from the template per table.
     */
    spTableIsMergeable(table) {
        if (!this.config.sp_merge_orders_enabled || !table) {
            return false;
        }
        return this.getTableOrders(table.id).some((order) => this.spOrderIsMergeable(order));
    },

    spOrderIsMergeable(order) {
        return Boolean(
            order &&
                !order.finalized &&
                order.lines.length > 0 &&
                order.payment_ids.length === 0
        );
    },

    /**
     * Other open orders, on the same floor as the given order, that can be
     * folded into it. Excludes the order itself, finalized/paid orders and
     * orders with no lines.
     */
    spMergeCandidates(order) {
        if (!this.config.sp_merge_orders_enabled || !order || !order.table_id) {
            return [];
        }
        const floorId = order.table_id.floor_id?.id;
        return this.models["pos.order"].filter(
            (other) =>
                other.uuid !== order.uuid &&
                other.table_id &&
                other.table_id.floor_id?.id === floorId &&
                this.spOrderIsMergeable(other)
        );
    },

    /**
     * Fold the selected source orders into ``destOrder`` and log the action.
     *
     * 18.0 has no reusable ``mergeOrders`` helper, so the line-consolidation
     * loop mirrors core ``transferOrder`` (same product-merge / append rules
     * and kitchen-preparation handling), minus the table reassignment.
     * Returns the labels actually merged.
     */
    async spMergeSelectedOrders(destOrder, sourceOrders) {
        const mergedLabels = [];
        for (const source of sourceOrders) {
            // Re-check at execution time: a payment may have started on another
            // terminal since the popup was opened.
            if (!this.spOrderIsMergeable(source) || source.uuid === destOrder.uuid) {
                continue;
            }
            mergedLabels.push(this.spOrderLabel(source));
            this.spFoldOrderInto(source, destOrder);
            await this.deleteOrders([source]);
        }
        if (mergedLabels.length) {
            if (typeof destOrder.id === "number") {
                await this.syncAllOrders({ orders: [destOrder] });
                // Best-effort audit trail; a failed log must not undo the merge.
                try {
                    await this.data.call("pos.order", "sp_log_merge", [
                        [destOrder.id],
                        mergedLabels,
                    ]);
                } catch {
                    // Chatter is informational only.
                }
            }
        }
        return mergedLabels;
    },

    /** Move every line of ``source`` into ``destOrder`` (consolidate or append). */
    spFoldOrderInto(source, destOrder) {
        for (const orphanLine of source.lines) {
            const adoptingLine = destOrder.lines.find((l) => l.can_be_merged_with(orphanLine));
            if (adoptingLine) {
                adoptingLine.merge(orphanLine);
                this.mergePreparationLines(
                    source.last_order_preparation_change.lines[orphanLine.preparationKey],
                    destOrder.last_order_preparation_change.lines[adoptingLine.preparationKey],
                    destOrder,
                    adoptingLine
                );
            } else {
                const serialized = orphanLine.serialize();
                serialized.order_id = destOrder.id;
                delete serialized.uuid;
                delete serialized.id;
                const newOrderLine = this.models["pos.order.line"].create(serialized, false, true);
                const preparationLine =
                    source.last_order_preparation_change.lines[orphanLine.preparationKey];
                if (preparationLine) {
                    const preparationLineCopy = { ...preparationLine };
                    preparationLineCopy.order_id = destOrder.id;
                    preparationLineCopy.uuid = newOrderLine.uuid;
                    destOrder.last_order_preparation_change.lines[newOrderLine.preparationKey] =
                        preparationLineCopy;
                    preparationLine.quantity = 0;
                }
            }
        }
    },

    spOrderLabel(order) {
        if (order.table_id) {
            return _t("Table %s", order.table_id.getName());
        }
        return order.floating_order_name || order.pos_reference || order.name || order.uuid;
    },
});
