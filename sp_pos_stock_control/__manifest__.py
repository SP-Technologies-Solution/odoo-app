# -*- coding: utf-8 -*-
{
    'name': 'SP POS Stock Visibility & Availability Control',
    'version': '18.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'summary': 'Display live product stock in POS and restrict sale of out-of-stock items',
    'description': """
Show the live stock of every product on the POS product grid and, optionally,
stop cashiers from selling what is not there.

Configured per point of sale (Point of Sale > Configuration > Settings):

* Show stock on the product cards, using On Hand, Forecasted or both.
* Out-of-stock behaviour: no restriction, warn & confirm, or hard block.

Quantities are evaluated from the source location of the POS operation type,
so each shop sees its own stock. Only storable products are considered.
    """,
    'website': 'https://sptechnologiessolution.com/',
    'author': 'SP Technologies',
    'depends': ['point_of_sale', 'stock'],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'sp_pos_stock_control/static/src/**/*',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
