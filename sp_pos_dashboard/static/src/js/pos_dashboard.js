/** @odoo-module **/
import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadBundle } from "@web/core/assets";
import { rpc } from "@web/core/network/rpc";
import { KpiCard } from "./components/kpi_card";
import { ChartWidget } from "./components/chart_widget";

// Odoo-native palette
const C = [
    "#017E84", "#875A7B", "#3AADAA", "#E06F5D",
    "#F4A460", "#56B3B4", "#A66DCD", "#E37D4F",
    "#28A745", "#6610F2",
];

// Maps our logical type → Chart.js type
const TYPE_MAP = {
    line: "line", area: "line",
    bar: "bar", hbar: "bar",
    pie: "pie", doughnut: "doughnut", polar: "polarArea",
};

function todayStr() { return new Date().toISOString().slice(0, 10); }
function daysAgoStr(n) {
    const d = new Date(); d.setDate(d.getDate() - n);
    return d.toISOString().slice(0, 10);
}

// Persist the applied filters so drilling down and coming back (which
// destroys and re-creates this client action) keeps the user's selection
// instead of resetting to defaults. Session-scoped: clears on a new tab.
const FILTERS_STORAGE_KEY = "sp_pos_dashboard.filters";
function loadSavedFilters() {
    try {
        const raw = sessionStorage.getItem(FILTERS_STORAGE_KEY);
        return raw ? JSON.parse(raw) : null;
    } catch (e) {
        return null;
    }
}
function saveFilters(filters) {
    try {
        sessionStorage.setItem(FILTERS_STORAGE_KEY, JSON.stringify(filters));
    } catch (e) {
        // storage unavailable (private mode / quota) — non-fatal
    }
}

export class PosDashboard extends Component {
    static template = "sp_pos_dashboard.Dashboard";
    static components = { KpiCard, ChartWidget };

    setup() {
        this.action = useService("action");
        this.notification = useService("notification");

        const defaultFilters = {
            date_from: daysAgoStr(0),
            date_to: todayStr(),
            period: "daily",
            session_id: false,
            config_id: false,
            company_id: false,
        };

        this.state = useState({
            loading: true,
            // Restore last-applied filters (survives drill-down/back); merge over
            // defaults so any newly-added filter keys are always present.
            filters: { ...defaultFilters, ...(loadSavedFilters() || {}) },
            // Chart type per section (logical names, see TYPE_MAP)
            chartTypes: {
                trend: "area",
                products: "hbar",
                customers: "hbar",
                categories: "doughnut",
                payments: "pie",
                staff: "bar",
            },
            currency_symbol: "",
            currency_position: "before",
            sessions: [], configs: [], companies: [],
            kpis: {
                total_sales: 0, total_orders: 0, aov: 0, total_items: 0,
                total_guests: 0, per_person_cost: 0,
                sales_growth: 0, orders_growth: 0, aov_growth: 0, items_growth: 0,
                guests_growth: 0, ppc_growth: 0,
            },
            topCustomers: [],
            topProducts: [],
            topCategories: [],
            salesTrend: [],
            paymentMethods: [],
            staffPerformance: [],
        });

        // ── Stable click handlers (arrow closures — 'this' always bound) ──────
        this.handlers = {
            product: (i) => {
                const p = this.state.topProducts[i];
                if (p?.id) this._open("pos.order.line", [["product_id", "=", p.id]], `Lines — ${p.name}`);
            },
            customer: (i) => {
                const c = this.state.topCustomers[i];
                if (c?.id) this._open("pos.order", [["partner_id", "=", c.id]], `Orders — ${c.name}`);
            },
            category: (i) => {
                const c = this.state.topCategories[i];
                if (c?.id) this._open("pos.order.line", [["product_id.pos_categ_ids", "in", [c.id]]], `Lines — ${c.name}`);
            },
            payment: (i) => {
                const p = this.state.paymentMethods[i];
                if (p?.id) this._open("pos.payment", [["payment_method_id", "=", p.id]], `Payments — ${p.name}`);
            },
            staff: (i) => {
                const s = this.state.staffPerformance[i];
                if (s?.id) this._open("pos.order", [["user_id", "=", s.id]], `Orders — ${s.name}`);
            },
        };

        onWillStart(async () => { await loadBundle("web.chartjs_lib"); });
        onMounted(async () => { await Promise.all([this._loadOptions(), this._loadData()]); });
    }

    // ── Data ──────────────────────────────────────────────────────────────────

    async _loadOptions() {
        try {
            const r = await rpc("/sp_pos_dashboard/get_filter_options");
            Object.assign(this.state, {
                sessions: r.sessions || [], configs: r.configs || [],
                companies: r.companies || [],
                currency_symbol: r.currency_symbol || "",
                currency_position: r.currency_position || "before",
            });
        } catch (e) { console.error("[Dashboard] options:", e); }
    }

    async _loadData() {
        this.state.loading = true;
        try {
            const r = await rpc("/sp_pos_dashboard/get_dashboard_data", {
                filters: { ...this.state.filters },
            });
            Object.assign(this.state, r);
        } catch (e) {
            this.notification.add("Failed to load dashboard data.", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    // ── Filters ───────────────────────────────────────────────────────────────

    onFilterChange(ev) {
        const f = ev.target.dataset.field;
        let v = ev.target.value;
        if (["session_id", "config_id", "company_id"].includes(f)) v = v ? parseInt(v, 10) : false;
        this.state.filters[f] = v;
        // Cascade: company change → reset shop + session
        if (f === "company_id") {
            this.state.filters.config_id = false;
            this.state.filters.session_id = false;
        }
        // Cascade: shop change → reset session
        if (f === "config_id") {
            this.state.filters.session_id = false;
        }
    }

    get filteredConfigs() {
        if (!this.state.filters.company_id) return this.state.configs;
        return this.state.configs.filter(c => c.company_id === this.state.filters.company_id);
    }

    get filteredSessions() {
        if (this.state.filters.config_id) {
            return this.state.sessions.filter(s => s.config_id === this.state.filters.config_id);
        }
        if (this.state.filters.company_id) {
            const configIds = new Set(this.filteredConfigs.map(c => c.id));
            return this.state.sessions.filter(s => configIds.has(s.config_id));
        }
        return this.state.sessions;
    }

    async onApplyFilters() {
        saveFilters(this.state.filters);
        await this._loadData();
    }

    async onRefresh() {
        await this._loadData();
        this.notification.add("Dashboard refreshed", { type: "success", sticky: false });
    }

    onExportExcel() {
        window.location.href =
            `/sp_pos_dashboard/export_excel?` +
            new URLSearchParams({ filters: JSON.stringify(this.state.filters) });
    }

    // ── Chart type switching ──────────────────────────────────────────────────

    setChartType(key, type) { this.state.chartTypes[key] = type; }

    /** Resolve logical type to Chart.js type string */
    cjsType(key) { return TYPE_MAP[this.state.chartTypes[key]] || "bar"; }

    /** Extra Chart.js options derived from logical type */
    cjsOpts(key) {
        const t = this.state.chartTypes[key];
        const circular = ["pie", "doughnut", "polar"].includes(t);
        const base = {
            plugins: { legend: { display: circular, position: "bottom" } },
        };
        if (t === "hbar") base.indexAxis = "y";
        return base;
    }

    // ── Drill-down ────────────────────────────────────────────────────────────

    // Build the active-filter domain for a drill-down target model, mirroring
    // the server-side `_build_order_domain` so opened records match the KPIs.
    _filterDomain(model) {
        const f = this.state.filters;
        // Path prefix to reach the pos.order from each drill-down model.
        let p = "";
        if (model === "pos.order.line") {
            p = "order_id.";
        } else if (model === "pos.payment") {
            p = "pos_order_id.";
        }
        const dom = [[`${p}state`, "in", ["paid", "done", "invoiced"]]];
        if (f.date_from) {
            dom.push([`${p}date_order`, ">=", f.date_from + " 00:00:00"]);
        }
        if (f.date_to) {
            dom.push([`${p}date_order`, "<=", f.date_to + " 23:59:59"]);
        }
        if (f.session_id) {
            dom.push([`${p}session_id`, "=", parseInt(f.session_id)]);
        }
        if (f.config_id) {
            dom.push([`${p}config_id`, "=", parseInt(f.config_id)]);
        }
        if (f.company_id) {
            dom.push([`${p}company_id`, "=", parseInt(f.company_id)]);
        }
        return dom;
    }

    _open(model, domain, name) {
        const fullDomain = [...this._filterDomain(model), ...domain];
        this.action.doAction({
            type: "ir.actions.act_window", name, res_model: model, domain: fullDomain,
            view_mode: "list,form", views: [[false, "list"], [false, "form"]],
        });
    }

    // ── Chart data getters ────────────────────────────────────────────────────

    get salesTrendData() {
        const isFill = this.state.chartTypes.trend === "area";
        return {
            labels: this.state.salesTrend.map((d) => d.label),
            datasets: [{
                label: "Sales", data: this.state.salesTrend.map((d) => d.total),
                borderColor: C[0], backgroundColor: isFill ? "rgba(1,126,132,.1)" : C[0],
                fill: isFill, tension: 0.45,
                pointBackgroundColor: C[0], pointRadius: 4, pointHoverRadius: 6,
                borderRadius: 4,
            }],
        };
    }

    get topProductsData() {
        const items = this.state.topProducts;
        return {
            labels: items.map((p) => p.name.length > 24 ? p.name.slice(0, 24) + "…" : p.name),
            datasets: [{
                label: "Revenue", data: items.map((p) => p.total),
                backgroundColor: items.map((_, i) => C[i % C.length]),
                borderRadius: 4, borderSkipped: false,
            }],
        };
    }

    get topCustomersData() {
        const items = this.state.topCustomers;
        return {
            labels: items.map((c) => c.name.length > 20 ? c.name.slice(0, 20) + "…" : c.name),
            datasets: [{
                label: "Revenue", data: items.map((c) => c.total),
                backgroundColor: items.map((_, i) => C[i % C.length]),
                borderRadius: 4, borderSkipped: false,
            }],
        };
    }

    get categoriesData() {
        const items = this.state.topCategories;
        return {
            labels: items.map((c) => c.name),
            datasets: [{
                data: items.map((c) => c.total),
                backgroundColor: items.map((_, i) => C[i % C.length]),
                borderWidth: 3, borderColor: "#fff", hoverOffset: 6,
                borderRadius: 4,
            }],
        };
    }

    get paymentData() {
        const items = this.state.paymentMethods;
        return {
            labels: items.map((p) => p.name),
            datasets: [{
                data: items.map((p) => p.total),
                backgroundColor: items.map((_, i) => C[i % C.length]),
                borderWidth: 3, borderColor: "#fff", hoverOffset: 6,
            }],
        };
    }

    get staffData() {
        const items = this.state.staffPerformance;
        return {
            labels: items.map((s) => s.name.split(" ")[0]),
            datasets: [{
                label: "Revenue", data: items.map((s) => s.total),
                backgroundColor: items.map((_, i) => C[i % C.length]),
                borderRadius: 4, borderSkipped: false,
            }],
        };
    }

    // ── Formatting ────────────────────────────────────────────────────────────

    fmt(value, type = "currency") {
        const n = value || 0;
        if (type === "currency") {
            const s = new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n);
            const sym = this.state.currency_symbol;
            return this.state.currency_position === "before" ? `${sym}${s}` : `${s}${sym}`;
        }
        return new Intl.NumberFormat("en-US").format(n);
    }
}

registry.category("actions").add("sp_pos_dashboard", PosDashboard);
