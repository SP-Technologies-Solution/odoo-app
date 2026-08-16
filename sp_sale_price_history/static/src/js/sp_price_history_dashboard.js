import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

/**
 * Four KPI tiles over sp.price.history.log.
 *
 * The aggregation is a single ORM call so the numbers stay testable server-side
 * and the browser does no arithmetic of its own.
 */
export class SpPriceHistoryDashboard extends Component {
    static template = "sp_sale_price_history.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ loading: true, data: null });

        onWillStart(async () => {
            this.state.data = await this.orm.call(
                "sp.price.history.log",
                "get_dashboard_data",
                []
            );
            this.state.loading = false;
        });
    }

    openChanges(extraContext = {}) {
        this.action.doAction("sp_sale_price_history.sp_price_history_log_action", {
            additionalContext: extraContext,
        });
    }
}

registry.category("actions").add("sp_price_history_dashboard", SpPriceHistoryDashboard);
