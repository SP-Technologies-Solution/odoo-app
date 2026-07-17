{
    'name': 'POS Dashboard',
    'version': '18.0.1.0',
    'category': 'Point of Sale',
    'summary': 'POS Dashboard | Point of Sale Dashboard | POS Analytics | POS Reports | POS Sales Analysis | Point of Sale Reports',
    'description': """
POS Dashboard - Point of Sale Analytics Dashboard
==================================================

Best POS Dashboard module for Odoo. Complete Point of Sale analytics, reporting, and sales analysis dashboard.

Key Features:
- POS Dashboard with KPI Cards (Total Sales, Orders, Average Order Value, Items Sold)
- POS Sales Trend Chart (Daily, Weekly, Monthly)
- POS Top Products Analysis
- POS Top Customers Report
- POS Category Distribution
- POS Payment Methods Analysis (Cash, Card)
- POS Staff Performance Report
- POS Session Analysis
- POS Shop Wise Report
- POS Excel Export
- Point of Sale Dashboard Filters (Date, Company, Shop, Session)
- POS Drill-Down Reports
- POS Custom Dashboard
- Point of Sale Analysis

Search Keywords:
pos dashboard, point of sale dashboard, pos analytics, pos reports, pos analysis,
pos custom dashboard, pos sales report, pos sales analysis, point of sale analysis,
point of sale reports, pos kpi, pos chart, pos excel report, pos staff report,
pos product analysis, pos customer analysis, pos payment report, pos session report,
dashboard pos, pos reporting, point of sale analytics
""",
    'author': 'SP Technologies Solution',
    'website': 'https://www.sptechnologiessolution.com',
    'depends': ['point_of_sale', 'base'],
    'data': [
        'security/pos_dashboard_security.xml',
        'views/pos_dashboard_action.xml',
        'views/pos_dashboard_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sp_pos_dashboard/static/src/scss/pos_dashboard.scss',
            'sp_pos_dashboard/static/src/xml/kpi_card.xml',
            'sp_pos_dashboard/static/src/xml/chart_widget.xml',
            'sp_pos_dashboard/static/src/xml/pos_dashboard.xml',
            'sp_pos_dashboard/static/src/js/components/kpi_card.js',
            'sp_pos_dashboard/static/src/js/components/chart_widget.js',
            'sp_pos_dashboard/static/src/js/pos_dashboard.js',
        ],
    },
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'price': 34,
    'currency': 'USD',
    'license': 'LGPL-3',
}
