import io
import json
from datetime import datetime, timedelta

from odoo import http
from odoo.http import request


class PosDashboardController(http.Controller):

    # ── Domain builders ───────────────────────────────────────────────────────

    def _build_order_domain(self, filters):
        domain = [('state', 'in', ['paid','done', 'invoiced'])]
        if filters.get('date_from'):
            domain.append(('date_order', '>=', filters['date_from'] + ' 00:00:00'))
        if filters.get('date_to'):
            domain.append(('date_order', '<=', filters['date_to'] + ' 23:59:59'))
        if filters.get('session_id'):
            domain.append(('session_id', '=', int(filters['session_id'])))
        if filters.get('config_id'):
            domain.append(('config_id', '=', int(filters['config_id'])))
        if filters.get('company_id'):
            domain.append(('company_id', '=', int(filters['company_id'])))
        return domain

    def _build_prev_domain(self, filters):
        domain = [('state', 'in', ['paid','done', 'invoiced'])]
        date_from = filters.get('date_from')
        date_to   = filters.get('date_to')
        if date_from and date_to:
            d_from    = datetime.strptime(date_from, '%Y-%m-%d')
            d_to      = datetime.strptime(date_to,   '%Y-%m-%d')
            delta     = d_to - d_from
            prev_to   = d_from - timedelta(days=1)
            prev_from = prev_to - delta
            domain.append(('date_order', '>=', prev_from.strftime('%Y-%m-%d') + ' 00:00:00'))
            domain.append(('date_order', '<=', prev_to.strftime('%Y-%m-%d')   + ' 23:59:59'))
        if filters.get('config_id'):
            domain.append(('config_id',  '=', int(filters['config_id'])))
        if filters.get('company_id'):
            domain.append(('company_id', '=', int(filters['company_id'])))
        return domain

    @staticmethod
    def _growth(current, previous):
        if not previous:
            return 100.0 if current else 0.0
        return round(((current - previous) / previous) * 100, 1)

    # ── POS category helper ───────────────────────────────────────────────────

    def _top_pos_categories(self, lines, top_n=5):
        """
        Aggregate order lines by pos.category (not internal product.category).
        Products may have multiple POS categories (pos_categ_ids is m2m in Odoo 18).
        We use the first category only to avoid double-counting revenue.
        """
        if not lines:
            return []

        # Batch-fetch all unique products to avoid N+1 queries
        products = lines.mapped('product_id')
        prod_categ = {}
        for prod in products:
            pos_categs = prod.pos_categ_ids if hasattr(prod, 'pos_categ_ids') else None
            if not pos_categs:
                # Fallback for older field name
                pos_categs = getattr(prod, 'pos_categ_id', None)
                if pos_categs:
                    pos_categs = [pos_categs]
            if pos_categs:
                categ = pos_categs[0]
                prod_categ[prod.id] = (categ.id, categ.name)
            else:
                prod_categ[prod.id] = (0, 'Uncategorized')

        categ_map = {}
        for line in lines:
            categ_id, categ_name = prod_categ.get(line.product_id.id, (0, 'Uncategorized'))
            if categ_id not in categ_map:
                categ_map[categ_id] = {'name': categ_name, 'id': categ_id, 'total': 0.0}
            categ_map[categ_id]['total'] += line.price_subtotal_incl

        result = sorted(categ_map.values(), key=lambda x: x['total'], reverse=True)[:top_n]
        for c in result:
            c['total'] = round(c['total'], 2)
        return result

    # ── Filter options ────────────────────────────────────────────────────────

    @http.route('/sp_pos_dashboard/get_filter_options', type='json', auth='user')
    def get_filter_options(self):
        env = request.env

        # Companies accessible to the current user
        companies = env['res.company'].search_read(
            [('id', 'in', env.user.company_ids.ids)],
            ['id', 'name'],
        )

        # Restrict to companies the current user is allowed to access
        allowed_company_ids = env.user.company_ids.ids

        # Active POS shops scoped to the user's allowed companies
        configs = env['pos.config'].search_read(
            [('active', '=', True), ('company_id', 'in', allowed_company_ids)],
            ['id', 'name', 'company_id'],
        )
        # Flatten company_id from [id, name] tuple → just id for easy JS comparison
        for cfg in configs:
            cfg['company_id'] = cfg['company_id'][0] if cfg.get('company_id') else False

        # Closed sessions scoped to the same allowed companies
        allowed_config_ids = [c['id'] for c in configs]
        sessions = env['pos.session'].search_read(
            [('state', 'in', ['closed', 'opened']), ('config_id', 'in', allowed_config_ids)],
            ['id', 'name', 'config_id'],
            limit=200,
            order='id desc',
        )
        for sess in sessions:
            sess['config_id'] = sess['config_id'][0] if sess.get('config_id') else False

        currency = env.company.currency_id
        return {
            'companies'       : companies,
            'configs'         : configs,
            'sessions'        : sessions,
            'currency_symbol' : currency.symbol   or '',
            'currency_position': currency.position or 'before',
        }

    # ── Main dashboard data ───────────────────────────────────────────────────

    @http.route('/sp_pos_dashboard/get_dashboard_data', type='json', auth='user')
    def get_dashboard_data(self, filters=None):
        if not filters:
            filters = {}

        env         = request.env
        PosOrder    = env['pos.order']
        PosOrderLine= env['pos.order.line']
        PosPayment  = env['pos.payment']

        domain      = self._build_order_domain(filters)
        prev_domain = self._build_prev_domain(filters)

        # ── KPIs ──────────────────────────────────────────────────────────────
        orders      = PosOrder.search(domain)
        prev_orders = PosOrder.search(prev_domain)

        total_sales   = sum(orders.mapped('amount_total'))
        total_orders  = len(orders)
        total_items   = sum(orders.mapped('lines').mapped('qty'))
        aov           = total_sales / total_orders if total_orders else 0.0

        has_guest_field = hasattr(PosOrder, 'customer_count')
        total_guests    = sum(orders.mapped('customer_count')) if has_guest_field else 0
        per_person_cost = round(total_sales / total_guests, 2) if total_guests else 0.0

        prev_sales        = sum(prev_orders.mapped('amount_total'))
        prev_total_orders = len(prev_orders)
        prev_items        = sum(prev_orders.mapped('lines').mapped('qty'))
        prev_aov          = prev_sales / prev_total_orders if prev_total_orders else 0.0
        prev_guests       = sum(prev_orders.mapped('customer_count')) if has_guest_field else 0
        prev_ppc          = round(prev_sales / prev_guests, 2) if prev_guests else 0.0

        kpis = {
            'total_sales'  : round(total_sales,  2),
            'total_orders' : total_orders,
            'aov'          : round(aov,           2),
            'total_items'  : round(total_items,   2),
            'total_guests'    : total_guests,
            'per_person_cost' : per_person_cost,
            'sales_growth' : self._growth(total_sales,  prev_sales),
            'orders_growth': self._growth(total_orders, prev_total_orders),
            'aov_growth'   : self._growth(aov,          prev_aov),
            'items_growth' : self._growth(total_items,  prev_items),
            'guests_growth': self._growth(total_guests, prev_guests),
            'ppc_growth'   : self._growth(per_person_cost, prev_ppc),
        }

        # ── Top 10 Customers ──────────────────────────────────────────────────
        cust_groups = PosOrder.read_group(
            domain + [('partner_id', '!=', False)],
            ['partner_id', 'amount_total:sum'],
            ['partner_id'],
            orderby='amount_total desc',
            limit=10,
        )
        top_customers = [{
            'name'  : g['partner_id'][1],
            'id'    : g['partner_id'][0],
            'total' : round(g['amount_total'], 2),
            'orders': g['partner_id_count'],
        } for g in cust_groups if g.get('partner_id')]

        # ── Top 10 Products ───────────────────────────────────────────────────
        line_domain = [('order_id', 'in', orders.ids)] if orders else [('id', '=', False)]
        prod_groups = PosOrderLine.read_group(
            line_domain,
            ['product_id', 'qty:sum', 'price_subtotal_incl:sum'],
            ['product_id'],
            orderby='price_subtotal_incl desc',
            limit=10,
        )
        top_products = [{
            'name' : g['product_id'][1],
            'id'   : g['product_id'][0],
            'qty'  : round(g['qty'],               2),
            'total': round(g['price_subtotal_incl'], 2),
        } for g in prod_groups if g.get('product_id')]

        # ── Top 5 POS Categories ──────────────────────────────────────────────
        lines          = PosOrderLine.search(line_domain) if orders else PosOrderLine.browse()
        top_categories = self._top_pos_categories(lines, top_n=5)

        # ── Sales Trend ───────────────────────────────────────────────────────
        period    = filters.get('period', 'monthly')
        group_map = {
            'daily'    : 'date_order:day',
            'weekly'   : 'date_order:week',
            'monthly'  : 'date_order:month',
            'quarterly': 'date_order:quarter',
            'yearly'   : 'date_order:year',
        }
        group_field  = group_map.get(period, 'date_order:month')
        trend_groups = PosOrder.read_group(domain, ['amount_total:sum'], [group_field])
        sales_trend  = [{
            'label': str(g.get(group_field, '')),
            'total': round(g.get('amount_total') or 0.0, 2),
        } for g in trend_groups]

        # ── Payment Methods ───────────────────────────────────────────────────
        pay_domain = [('pos_order_id', 'in', orders.ids)] if orders else [('id', '=', False)]
        pay_groups = PosPayment.read_group(
            pay_domain,
            ['payment_method_id', 'amount:sum'],
            ['payment_method_id'],
            orderby='amount desc',
        )
        payment_methods = [{
            'name' : g['payment_method_id'][1] if g.get('payment_method_id') else 'Unknown',
            'id'   : g['payment_method_id'][0] if g.get('payment_method_id') else False,
            'total': round(g.get('amount') or 0.0, 2),
        } for g in pay_groups]

        # ── Staff Performance ─────────────────────────────────────────────────
        staff_groups = PosOrder.read_group(
            domain,
            ['user_id', 'amount_total:sum'],
            ['user_id'],
            orderby='amount_total desc',
            limit=10,
        )
        staff_performance = [{
            'name'  : g['user_id'][1] if g.get('user_id') else 'Unknown',
            'id'    : g['user_id'][0] if g.get('user_id') else False,
            'total' : round(g.get('amount_total') or 0.0, 2),
            'orders': g.get('user_id_count', 0),
        } for g in staff_groups]

        return {
            'kpis'            : kpis,
            'topCustomers'    : top_customers,
            'topProducts'     : top_products,
            'topCategories'   : top_categories,
            'salesTrend'      : sales_trend,
            'paymentMethods'  : payment_methods,
            'staffPerformance': staff_performance,
        }

    # ── Excel Export ──────────────────────────────────────────────────────────

    @http.route('/sp_pos_dashboard/export_excel', type='http', auth='user')
    def export_excel(self, filters=None, **kwargs):
        try:
            import xlsxwriter
        except ImportError:
            return request.make_response(
                'xlsxwriter is not installed. Run: pip install xlsxwriter',
                headers=[('Content-Type', 'text/plain')],
            )

        filters = json.loads(filters) if filters else {}
        data    = self._get_dashboard_data_raw(filters)

        output = io.BytesIO()
        wb     = xlsxwriter.Workbook(output, {'in_memory': True})

        hdr  = wb.add_format({'bold': True, 'bg_color': '#017E84', 'font_color': 'white', 'border': 1, 'align': 'center'})
        cell = wb.add_format({'border': 1})
        num  = wb.add_format({'border': 1, 'num_format': '#,##0.00'})
        pct  = wb.add_format({'border': 1, 'num_format': '0.0"%"'})

        def sheet(name, headers, rows, fmts):
            ws = wb.add_worksheet(name)
            for col, h in enumerate(headers):
                ws.write(0, col, h, hdr)
                ws.set_column(col, col, max(len(h) + 4, 18))
            for i, row in enumerate(rows, 1):
                for col, (val, fmt) in enumerate(zip(row, fmts)):
                    ws.write(i, col, val, fmt)

        kpi = data['kpis']
        sheet('KPIs',
              ['Metric', 'Value', 'vs Prev Period (%)'],
              [('Total Sales',     kpi['total_sales'],  kpi['sales_growth']),
               ('Total Orders',    kpi['total_orders'], kpi['orders_growth']),
               ('Avg Order Value', kpi['aov'],          kpi['aov_growth']),
               ('Items Sold',      kpi['total_items'],  kpi['items_growth']),
               ('Total Guests',    kpi['total_guests'], kpi['guests_growth']),
               ('Per Person Cost', kpi['per_person_cost'], kpi['ppc_growth'])],
              [cell, num, pct])

        sheet('Top Customers',
              ['Customer', 'Orders', 'Total Sales'],
              [(r['name'], r['orders'], r['total']) for r in data['topCustomers']],
              [cell, cell, num])

        sheet('Top Products',
              ['Product', 'Qty Sold', 'Total Sales'],
              [(r['name'], r['qty'], r['total']) for r in data['topProducts']],
              [cell, num, num])

        sheet('POS Categories',
              ['POS Category', 'Total Sales'],
              [(r['name'], r['total']) for r in data['topCategories']],
              [cell, num])

        sheet('Payment Methods',
              ['Payment Method', 'Total'],
              [(r['name'], r['total']) for r in data['paymentMethods']],
              [cell, num])

        sheet('Staff Performance',
              ['Cashier', 'Orders', 'Total Sales'],
              [(r['name'], r['orders'], r['total']) for r in data['staffPerformance']],
              [cell, cell, num])

        wb.close()
        output.seek(0)
        return request.make_response(
            output.read(),
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', 'attachment; filename="pos_dashboard.xlsx"'),
            ],
        )

    def _get_dashboard_data_raw(self, filters):
        """Internal helper used by the export route (bypasses HTTP decorator)."""
        env          = request.env
        PosOrder     = env['pos.order']
        PosOrderLine = env['pos.order.line']
        PosPayment   = env['pos.payment']

        domain      = self._build_order_domain(filters)
        prev_domain = self._build_prev_domain(filters)
        orders      = PosOrder.search(domain)
        prev_orders = PosOrder.search(prev_domain)

        total_sales  = sum(orders.mapped('amount_total'))
        total_orders = len(orders)
        total_items  = sum(orders.mapped('lines').mapped('qty'))
        aov          = total_sales / total_orders if total_orders else 0.0

        has_guest_field = hasattr(PosOrder, 'customer_count')
        total_guests    = sum(orders.mapped('customer_count')) if has_guest_field else 0
        per_person_cost = round(total_sales / total_guests, 2) if total_guests else 0.0

        prev_sales        = sum(prev_orders.mapped('amount_total'))
        prev_total_orders = len(prev_orders)
        prev_items        = sum(prev_orders.mapped('lines').mapped('qty'))
        prev_aov          = prev_sales / prev_total_orders if prev_total_orders else 0.0
        prev_guests       = sum(prev_orders.mapped('customer_count')) if has_guest_field else 0
        prev_ppc          = round(prev_sales / prev_guests, 2) if prev_guests else 0.0

        kpis = {
            'total_sales'  : round(total_sales,  2), 'total_orders': total_orders,
            'aov'          : round(aov,           2), 'total_items' : round(total_items, 2),
            'total_guests'    : total_guests,
            'per_person_cost' : per_person_cost,
            'sales_growth' : self._growth(total_sales,  prev_sales),
            'orders_growth': self._growth(total_orders, prev_total_orders),
            'aov_growth'   : self._growth(aov,          prev_aov),
            'items_growth' : self._growth(total_items,  prev_items),
            'guests_growth': self._growth(total_guests, prev_guests),
            'ppc_growth'   : self._growth(per_person_cost, prev_ppc),
        }

        line_domain = [('order_id', 'in', orders.ids)] if orders else [('id', '=', False)]

        # POS categories
        lines          = PosOrderLine.search(line_domain) if orders else PosOrderLine.browse()
        top_categories = self._top_pos_categories(lines, top_n=5)

        # Top customers
        cust_groups = PosOrder.read_group(
            domain + [('partner_id', '!=', False)],
            ['partner_id', 'amount_total:sum'], ['partner_id'],
            orderby='amount_total desc', limit=10,
        )
        top_customers = [{'name': g['partner_id'][1], 'id': g['partner_id'][0],
                          'total': round(g['amount_total'], 2), 'orders': g['partner_id_count']}
                         for g in cust_groups if g.get('partner_id')]

        # Top products
        prod_groups = PosOrderLine.read_group(
            line_domain, ['product_id', 'qty:sum', 'price_subtotal_incl:sum'], ['product_id'],
            orderby='price_subtotal_incl desc', limit=10,
        )
        top_products = [{'name': g['product_id'][1], 'id': g['product_id'][0],
                         'qty': round(g['qty'], 2), 'total': round(g['price_subtotal_incl'], 2)}
                        for g in prod_groups if g.get('product_id')]

        # Payment methods
        pay_domain = [('pos_order_id', 'in', orders.ids)] if orders else [('id', '=', False)]
        pay_groups = PosPayment.read_group(
            pay_domain, ['payment_method_id', 'amount:sum'], ['payment_method_id'],
            orderby='amount desc',
        )
        payment_methods = [{'name': g['payment_method_id'][1] if g.get('payment_method_id') else 'Unknown',
                            'id': g['payment_method_id'][0] if g.get('payment_method_id') else False,
                            'total': round(g.get('amount') or 0.0, 2)} for g in pay_groups]

        # Staff
        staff_groups = PosOrder.read_group(
            domain, ['user_id', 'amount_total:sum'], ['user_id'],
            orderby='amount_total desc', limit=10,
        )
        staff_performance = [{'name': g['user_id'][1] if g.get('user_id') else 'Unknown',
                              'id': g['user_id'][0] if g.get('user_id') else False,
                              'total': round(g.get('amount_total') or 0.0, 2),
                              'orders': g.get('user_id_count', 0)} for g in staff_groups]

        # Trend
        period    = filters.get('period', 'monthly')
        group_map = {'daily': 'date_order:day', 'weekly': 'date_order:week',
                     'monthly': 'date_order:month', 'quarterly': 'date_order:quarter',
                     'yearly': 'date_order:year'}
        group_field  = group_map.get(period, 'date_order:month')
        trend_groups = PosOrder.read_group(domain, ['amount_total:sum'], [group_field])
        sales_trend  = [{'label': str(g.get(group_field, '')),
                         'total': round(g.get('amount_total') or 0.0, 2)} for g in trend_groups]

        return {
            'kpis': kpis, 'topCustomers': top_customers, 'topProducts': top_products,
            'topCategories': top_categories, 'salesTrend': sales_trend,
            'paymentMethods': payment_methods, 'staffPerformance': staff_performance,
        }
