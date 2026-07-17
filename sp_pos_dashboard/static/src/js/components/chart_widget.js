/** @odoo-module **/
import { Component, useRef, onMounted, onWillUnmount, useEffect } from "@odoo/owl";

const CIRCULAR = new Set(["doughnut", "pie", "polarArea"]);

export class ChartWidget extends Component {
    static template = "sp_pos_dashboard.ChartWidget";
    static props = {
        type    : String,
        chartKey: { type: String, optional: true }, // logical key — drives recreation
        data    : Object,
        options : { type: Object, optional: true },
        height  : { type: String,   optional: true },
        onClick : { type: Function, optional: true },
    };
    static defaultProps = { options: {}, height: "300px" };

    setup() {
        this.canvasRef  = useRef("canvas");
        this.chart      = null;
        this._activeKey = null; // tracks the LOGICAL type, not Chart.js type

        onMounted (() => this._sync());
        onWillUnmount(() => this._destroy());

        // Track chartKey (logical type) + data — recreate on key change, update on data change
        useEffect(
            () => this._sync(),
            () => [this.props.chartKey || this.props.type, this.props.data]
        );
    }

    // ── Internal ──────────────────────────────────────────────────────────────

    _destroy() {
        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }
        // Clear canvas: prevents Chart.js "ghost" when reusing canvas after destroy
        const el = this.canvasRef.el;
        if (el) {
            try {
                const ctx = el.getContext("2d");
                if (ctx) ctx.clearRect(0, 0, el.width, el.height);
            } catch (_) { /* ignore cross-origin canvas errors */ }
        }
        this._activeKey = null;
    }

    _sync() {
        const el = this.canvasRef.el;
        if (!el || !window.Chart) return;

        const hasData = this.props.data?.datasets?.some((d) => (d.data?.length || 0) > 0);
        if (!hasData) { this._destroy(); return; }

        // The "key" is what uniquely identifies a chart configuration.
        // Using the logical type (e.g. 'hbar', 'area') instead of the cjs type
        // ('bar', 'line') ensures recreation even when the cjs type is the same.
        const key = this.props.chartKey || this.props.type;

        if (this.chart && this._activeKey === key) {
            // Same logical chart type → just push new data, no flicker
            this.chart.data = this.props.data;
            this.chart.update("none");
        } else {
            // Key changed (or first render) → must destroy + recreate with new options
            this._destroy();
            this._activeKey = key;
            this.chart = new window.Chart(el, {
                type   : this.props.type,
                data   : this.props.data,
                options: this._buildOpts(),
            });
        }
    }

    _buildOpts() {
        const isCircular = CIRCULAR.has(this.props.type);
        const extra      = this.props.options || {};

        // Legend: caller can force display via extra.plugins.legend.display
        const legendDisplay = extra.plugins?.legend?.display ?? isCircular;

        const opts = {
            responsive         : true,
            maintainAspectRatio: false,
            animation          : { duration: 380 },
            // Hover state changes (bar highlight, slice offset, point grow) are instant
            transitions: {
                active: { animation: { duration: 0 } },
            },
            // Single source of truth for both tooltip AND onHover element detection
            interaction: {
                mode     : isCircular ? "nearest" : "index",
                intersect: false,
            },
            plugins: {
                legend: {
                    display : legendDisplay,
                    position: "bottom",
                    labels  : {
                        usePointStyle: true,
                        padding      : 14,
                        font         : { size: 12, family: "'Lato', sans-serif" },
                    },
                },
                tooltip: {
                    backgroundColor: "rgba(30,30,30,.88)",
                    padding        : 10,
                    cornerRadius   : 6,
                    titleFont      : { size: 12, weight: "600" },
                    bodyFont       : { size: 12 },
                },
            },
        };

        // Cartesian charts need axes; circular charts do not
        if (!isCircular) {
            opts.scales = {
                x: {
                    grid : { display: false },
                    ticks: { font: { size: 11 }, maxRotation: 35 },
                },
                y: {
                    beginAtZero: true,
                    grid       : { color: "rgba(0,0,0,.05)", drawBorder: false },
                    ticks      : { font: { size: 11 } },
                },
            };
        }

        // Horizontal bar: swap axes
        if (extra.indexAxis) opts.indexAxis = extra.indexAxis;

        // Drill-down click handler
        if (this.props.onClick) {
            opts.onClick = (_e, els) => {
                if (els.length) this.props.onClick(els[0].index);
            };
            // Always show pointer over the whole chart area — no flicker between elements
            opts.onHover = (e) => {
                e.native.target.style.cursor = "pointer";
            };
        }

        return opts;
    }
}
