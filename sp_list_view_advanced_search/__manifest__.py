# -*- coding: utf-8 -*-
{
    'name': 'Advanced Column Filters for List Views',
    'version': '18.0.1.0.0',
    'author': 'SP Technologies Solution',
    'summary': 'Multi-condition, per-column filtering directly in list view headers',
    'description': """
Advanced Column Filters for List Views
======================================

A small filter icon appears in each column header — click it to filter that
column through a compact popover, without a permanent extra row eating up
screen space.

Key capabilities
----------------
* One filter icon per column, opening a popover matched to the field's own type
* Text search, numeric ranges, date ranges, multi-select dropdowns,
  many2one / many2many autocomplete, boolean tri-state and priority-star filtering
* Stack multiple conditions on the same column (OR'd), across columns (AND'd)
* Applied filters sync live with the standard search bar facets — remove them
  from the popover or from the facet chip and both stay in sync
* Pure client-side (OWL) extension of the List renderer — no new models,
  no data migration, works on every model's list view in Community and Enterprise
    """,
    'category': 'Extra Tools',
    'website': 'https://sptechnologiessolution.com/',
    'license': 'LGPL-3',
    'depends': ['base', 'web'],
    'data': [],
    'assets': {
        'web.assets_backend': [
            'sp_list_view_advanced_search/static/src/scss/variables.scss',
            'sp_list_view_advanced_search/static/src/scss/list_view_advanced_search.scss',
            'sp_list_view_advanced_search/static/src/js/utils/domain_builder.js',
            'sp_list_view_advanced_search/static/src/js/column_filter_manager.js',
            'sp_list_view_advanced_search/static/src/js/widgets/many2x_filter_input.js',
            'sp_list_view_advanced_search/static/src/js/column_filter_popover.js',
            'sp_list_view_advanced_search/static/src/js/list_renderer_patch.js',
            'sp_list_view_advanced_search/static/src/xml/many2x_filter_input.xml',
            'sp_list_view_advanced_search/static/src/xml/column_filter_popover.xml',
        ],
        'web.assets_tests': [
            'sp_list_view_advanced_search/static/tests/tours/sp_list_view_advanced_search_tour.js',
        ],
    },
    'images': ['static/description/banner.png'],
    'price': 7.0,
    'currency': 'USD',
    'installable': True,
    'application': False,
    'auto_install': False,
}
