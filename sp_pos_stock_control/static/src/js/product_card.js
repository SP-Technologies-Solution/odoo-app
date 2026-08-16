import { patch } from "@web/core/utils/patch";
import { ProductCard } from "@point_of_sale/app/generic_components/product_card/product_card";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { spStockBadge } from "@sp_pos_stock_control/js/sp_stock_utils";

patch(ProductCard.prototype, {
    setup() {
        super.setup(...arguments);
        this.pos = usePos();
    },

    get spStockBadge() {
        return spStockBadge(this.pos.config, this.props.product);
    },
});
