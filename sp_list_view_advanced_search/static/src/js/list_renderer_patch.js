/** @odoo-module **/

import { useState, onMounted, onPatched } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { useBus } from "@web/core/utils/hooks";
import { usePopover } from "@web/core/popover/popover_hook";
import { ListRenderer } from "@web/views/list/list_renderer";
import { ColumnFilterManager } from "./column_filter_manager";
import { ColumnFilterPopover } from "./column_filter_popover";
import { SUPPORTED_FIELD_TYPES } from "./utils/domain_builder";

/**
 * Extends the List renderer to add a per-column filter funnel icon in each
 * supported column header.
 *
 * The icon is injected into the rendered DOM (in onMounted / onPatched) rather
 * than through QWeb template inheritance. Several core/enterprise renderers
 * (e.g. account's AccountMoveListRenderer) use their OWN template — a
 * `t-inherit-mode="primary"` copy of web.ListRenderer — which a template
 * extension of web.ListRenderer does not reach. Every one of those copies
 * still renders the same `t-ref="table"` <table>, so injecting into
 * `tableRef.el` covers all list views with a single code path.
 *
 * Everything is a no-op when the list has no SearchModel (e.g. an embedded
 * x2many list inside a form), keeping the extension non-invasive.
 */
patch(ListRenderer.prototype, {
    setup() {
        super.setup();
        this.spSearchModel = this.env.searchModel;
        if (this.spSearchModel) {
            this.spFilterManager = new ColumnFilterManager(this.spSearchModel);
            // Subscribe THIS component to the shared manager state so header
            // badges re-render (and re-inject) when filters change.
            this.spFilterState = useState(this.spFilterManager.state);
            this.spFilterPopover = usePopover(ColumnFilterPopover, {
                position: "bottom-start",
                popoverClass: "o_sp_column_filter_popover",
            });
            useBus(this.spSearchModel, "update", () => this.spFilterManager.reconcile());
            onMounted(() => this.spInjectFilterIcons());
            onPatched(() => this.spInjectFilterIcons());
        }
    },

    /** Field type for a column name, or null. */
    spFieldType(fieldName) {
        const field = this.props.list.fields[fieldName];
        return field ? field.type : null;
    },

    spIsFilterable(fieldName, th) {
        const type = this.spFieldType(fieldName);
        if (!type || !SUPPORTED_FIELD_TYPES.includes(type)) {
            return false;
        }
        // Skip handle/sequence drag columns.
        return !th.classList.contains("o_handle_cell");
    },

    /**
     * Walk the rendered header cells and make sure each supported column has a
     * funnel icon, kept in sync with the active-filter state.
     */
    spInjectFilterIcons() {
        const table = this.tableRef && this.tableRef.el;
        if (!table || !this.spFilterManager) {
            return;
        }
        const headers = table.querySelectorAll("thead th[data-name]");
        for (const th of headers) {
            const fieldName = th.dataset.name;
            // Header label wrapper: ".d-flex.align-items-center" on 19.0,
            // plain ".d-flex" on 17.0/18.0 — match both with a direct-child .d-flex.
            const container = th.querySelector(":scope > .d-flex");
            if (!container || !this.spIsFilterable(fieldName, th)) {
                continue;
            }
            let icon = container.querySelector(":scope > .o_sp_column_filter_icon");
            if (!icon) {
                icon = document.createElement("i");
                icon.className = "o_sp_column_filter_icon fa fa-filter me-2";
                icon.setAttribute("role", "button");
                icon.title = "Filter this column";
                icon.addEventListener("click", (ev) => {
                    ev.stopPropagation();
                    ev.preventDefault();
                    this.spOpenFilter(ev.currentTarget, th, fieldName);
                });
                // Block the header's sort/pointer handlers.
                icon.addEventListener("pointerup", (ev) => ev.stopPropagation());
                icon.addEventListener("pointerdown", (ev) => ev.stopPropagation());
                container.insertBefore(icon, container.firstChild);
            }
            icon.classList.toggle(
                "o_sp_column_filter_active",
                this.spFilterManager.hasFilter(fieldName)
            );
        }
    },

    spOpenFilter(target, th, fieldName) {
        const field = this.props.list.fields[fieldName];
        const labelEl = th.querySelector(":scope > .d-flex span");
        const label = (labelEl && labelEl.textContent.trim()) || field.string || fieldName;
        this.spFilterPopover.open(target, {
            fieldName,
            label,
            field,
            manager: this.spFilterManager,
        });
    },
});
