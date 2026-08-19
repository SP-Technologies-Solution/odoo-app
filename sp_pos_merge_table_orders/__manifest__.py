{
    'name': 'SP POS Merge Table Orders',
    'version': '18.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'summary': 'Merge open POS table orders into one order directly from the '
               'Point of Sale screen',
    'description': """
Combine two or more open restaurant table orders into a single order without
leaving the Point of Sale screen.

Enabled per point of sale (Point of Sale > Configuration > Settings). Once on:

* Tables holding another open, unpaid order on the current floor are flagged on
  the floor plan with a merge badge.
* A "Merge Orders" action button appears in the POS control-button panel while a
  table order is open and at least one other mergeable order exists on the same
  floor.
* The cashier picks one or more of those orders in a selection dialog and
  confirms; their lines are folded into the current order (identical lines have
  their quantities summed, everything else is appended), the source tables are
  freed, and the action is logged on the resulting order's chatter with who
  merged what and when.

Orders that already have a payment in progress cannot be merged, and merging is
scoped to the same shop and floor.
    """,
    'author': 'SP Technologies Solution',
    'website': 'https://sptechnologiessolution.com/',
    'license': 'LGPL-3',
    'price': 8.0,
    'currency': 'USD',
    'depends': ['point_of_sale', 'pos_restaurant'],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'sp_pos_merge_table_orders/static/src/**/*',
        ],
    },
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
