import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { ask } from "@point_of_sale/app/store/make_awaitable_dialog";
import { _t } from "@web/core/l10n/translation";
import { spIsStorable, spAvailableQty, spRound } from "@sp_pos_stock_control/js/sp_stock_utils";

patch(PosStore.prototype, {
    async addLineToCurrentOrder(vals, opts = {}, configure = true) {
        if (!(await this.spAllowSale(vals.product_id))) {
            return;
        }
        return super.addLineToCurrentOrder(vals, opts, configure);
    },

    spOrderedQty(product) {
        const order = this.get_order();
        if (!order) {
            return 0;
        }
        return order
            .get_orderlines()
            .reduce(
                (total, line) =>
                    line.get_product()?.id === product.id ? total + line.get_quantity() : total,
                0
            );
    },

    async spAllowSale(product) {
        if (this.config.sp_out_of_stock_mode === "off" || !spIsStorable(product)) {
            return true;
        }
        const available = spAvailableQty(this.config, product, this.spOrderedQty(product));
        if (available > 0) {
            return true;
        }
        if (this.config.sp_out_of_stock_mode === "block") {
            this.notification.add(
                _t("%s is out of stock and cannot be sold.", product.display_name),
                { type: "danger" }
            );
            return false;
        }
        return await ask(this.dialog, {
            title: _t("Out of stock"),
            body: _t(
                "%s has no stock left (%s). Add it to the order anyway?",
                product.display_name,
                spRound(available)
            ),
            confirmLabel: _t("Add anyway"),
            cancelLabel: _t("Cancel"),
        });
    },
});
