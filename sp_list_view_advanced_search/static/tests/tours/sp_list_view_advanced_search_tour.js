/** @odoo-module **/

import { registry } from "@web/core/registry";

/**
 * Smoke tour: open the Contacts list, apply a "contains" text filter on the
 * Name column through the header funnel, and assert a facet chip appears.
 *
 * Run with:
 *   odoo -i sp_list_view_advanced_search --test-tags /sp_list_view_advanced_search
 * or trigger `sp_list_view_advanced_search_tour` from the tour manager.
 */
registry.category("web_tour.tours").add("sp_list_view_advanced_search_tour", {
    url: "/odoo/contacts",
    steps: () => [
        {
            trigger: ".o_list_view thead th[data-name='display_name'] .o_sp_column_filter_icon",
            content: "Open the column filter popover for the Name column",
            run: "click",
        },
        {
            trigger: ".o_sp_cf_popover .o_sp_cf_condition input[type='text']",
            content: "Type a search term",
            run: "edit Azure",
        },
        {
            trigger: ".o_sp_cf_popover .o_sp_cf_apply:not([disabled])",
            content: "Apply the filter",
            run: "click",
        },
        {
            trigger: ".o_searchview .o_facet_values:contains('Azure')",
            content: "The applied column filter shows as a removable search facet",
        },
        {
            trigger: ".o_list_view thead th[data-name='display_name'] .o_sp_column_filter_active",
            content: "The column header keeps its active-filter badge",
        },
    ],
});
