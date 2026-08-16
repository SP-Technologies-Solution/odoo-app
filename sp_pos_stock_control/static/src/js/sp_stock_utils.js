/**
 * Helpers shared by the product card and the POS store.
 *
 * `product` is the POS product record (is_storable), `config` the current
 * pos.config record.
 */

export function spIsStorable(product) {
    return Boolean(product) && Boolean(product.is_storable);
}

export function spRound(qty) {
    return Math.round((qty || 0) * 100) / 100;
}

export function spOnHand(product) {
    return (product && product.qty_available) || 0;
}

export function spForecast(product) {
    return (product && product.virtual_available) || 0;
}

// Quantity the out-of-stock check is based on. `both` deliberately falls back
// to the on hand quantity: that is what is physically sellable.
export function spDecisionQty(config, product) {
    return config.sp_stock_display_type === "forecasted"
        ? spForecast(product)
        : spOnHand(product);
}

export function spStockBadge(config, product) {
    if (!config.sp_display_stock || !spIsStorable(product)) {
        return null;
    }
    let text;
    if (config.sp_stock_display_type === "both") {
        text = `${spRound(spOnHand(product))} / ${spRound(spForecast(product))}`;
    } else if (config.sp_stock_display_type === "forecasted") {
        text = String(spRound(spForecast(product)));
    } else {
        text = String(spRound(spOnHand(product)));
    }
    return { text, out: spDecisionQty(config, product) <= 0 };
}

export function spAvailableQty(config, product, orderedQty) {
    return spDecisionQty(config, product) - (orderedQty || 0);
}
