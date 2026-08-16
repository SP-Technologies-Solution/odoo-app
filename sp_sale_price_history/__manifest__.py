# -*- coding: utf-8 -*-
{
    'name': 'SP Sales Price Change History',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'summary': 'Automatically track every Sales Price change with a dashboard, audit list and PDF/XLSX exports',
    'description': """
Every change to a product's Sales Price is written to an audit log, with no
manual step and no record when the price did not actually move.

* Old price, new price, difference, percentage, date, user, company, currency.
* Price History smart button plus Previous Price and Last Price Change on the
  product form.
* KPI dashboard: total changes, products updated, largest increase, largest
  decrease.
* Audit list with date, increase/decrease and grouping filters.
* Export a date range to PDF or XLSX.
* The log is append-only: it is written by the price-change hook and nothing
  else, and only a Price History Manager can delete an entry.
    """,
    'website': 'https://sptechnologiessolution.com/',
    'author': 'SP Technologies',
    'depends': ['product', 'mail'],
    'data': [
        'security/sp_price_history_security.xml',
        'security/ir.model.access.csv',
        'report/sp_price_history_report.xml',
        'report/sp_price_history_report_templates.xml',
        'wizard/sp_price_history_export_wizard_views.xml',
        'views/sp_price_history_views.xml',
        'views/product_template_views.xml',
        'views/sp_price_history_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sp_sale_price_history/static/src/css/sp_price_history_dashboard.css',
            'sp_sale_price_history/static/src/js/sp_price_history_dashboard.js',
            'sp_sale_price_history/static/src/xml/sp_price_history_dashboard.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
