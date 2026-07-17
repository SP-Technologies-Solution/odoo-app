/** @odoo-module **/
import { Component } from "@odoo/owl";

export class KpiCard extends Component {
    static template = "sp_pos_dashboard.KpiCard";
    static props = {
        title: String,
        value: Number,
        growth: Number,
        icon: String,
        accentColor: String,
        loading: { type: Boolean, optional: true },
        type: { type: String, optional: true },
        currencySymbol: { type: String, optional: true },
        currencyPosition: { type: String, optional: true },
        onClick: { type: Function, optional: true },
    };
    static defaultProps = {
        type: "number",
        currencySymbol: "",
        currencyPosition: "before",
        loading: false,
    };

    get formattedValue() {
        const { type, value, currencySymbol, currencyPosition } = this.props;
        const num = new Intl.NumberFormat("en-US", {
            minimumFractionDigits: type === "currency" ? 2 : 0,
            maximumFractionDigits: type === "currency" ? 2 : 0,
        }).format(value || 0);
        if (type === "currency") {
            return currencyPosition === "before" ? `${currencySymbol}${num}` : `${num}${currencySymbol}`;
        }
        return num;
    }

    get isPositive() { return this.props.growth >= 0; }
    get growthAbs() { return Math.abs(this.props.growth); }

    handleClick() {
        if (this.props.onClick) this.props.onClick();
    }
}
