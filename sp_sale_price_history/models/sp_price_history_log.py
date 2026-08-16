# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.sql import create_index

# Set only by the price-change hook. Without it, create() is refused, which is
# what makes the log append-only rather than merely "hard to edit".
SP_LOGGING_KEY = 'sp_price_history_logging'


class SpPriceHistoryLog(models.Model):
    _name = 'sp.price.history.log'
    _description = "Sales Price Change"
    _order = 'change_date desc, id desc'
    _rec_name = 'product_tmpl_id'

    product_tmpl_id = fields.Many2one(
        'product.template', string="Product", required=True,
        ondelete='cascade', index=True)
    product_id = fields.Many2one(
        'product.product', string="Variant", ondelete='set null',
        help="The variant that triggered the change, when the write came "
             "through one.")
    currency_id = fields.Many2one('res.currency', required=True)
    old_price = fields.Monetary(string="Old Price", required=True)
    new_price = fields.Monetary(string="New Price", required=True)
    price_diff = fields.Monetary(
        string="Difference", compute='_compute_price_diff', store=True)
    price_diff_percent = fields.Float(
        string="Change (%)", compute='_compute_price_diff', store=True,
        digits=(16, 2))
    change_date = fields.Datetime(
        string="Change Date", required=True, index=True,
        default=fields.Datetime.now)
    user_id = fields.Many2one(
        'res.users', string="Changed By", required=True, index=True,
        default=lambda self: self.env.user)
    company_id = fields.Many2one(
        'res.company', string="Company", required=True, index=True,
        default=lambda self: self.env.company)
    note = fields.Text(string="Note")

    # ------------------------------------------------------------------
    # Indexes
    # ------------------------------------------------------------------
    def _auto_init(self):
        """Composite indexes for the two queries that actually get big.

        The smart button and product filter hit (product, date); the dashboard
        and export hit (company, date).
        """
        res = super()._auto_init()
        create_index(
            self.env.cr, 'sp_price_history_log_product_date_idx',
            self._table, ['product_tmpl_id', 'change_date'])
        create_index(
            self.env.cr, 'sp_price_history_log_company_date_idx',
            self._table, ['company_id', 'change_date'])
        return res

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('old_price', 'new_price')
    def _compute_price_diff(self):
        for log in self:
            log.price_diff = log.new_price - log.old_price
            if log.old_price:
                log.price_diff_percent = (log.price_diff / log.old_price) * 100.0
            else:
                # No meaningful percentage from a zero base; 0 reads better in
                # the list than an arbitrary 100 or a division error.
                log.price_diff_percent = 0.0

    # ------------------------------------------------------------------
    # Append-only guards
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get(SP_LOGGING_KEY) and not self.env.su:
            raise UserError(_(
                "Price history entries are written automatically when a "
                "product's sales price changes. They cannot be created by hand."))
        return super().create(vals_list)

    def write(self, vals):
        """Only the free-text note stays editable; the figures do not."""
        if not self.env.su:
            locked = set(vals) - {'note'}
            if locked:
                raise UserError(_(
                    "A price history entry cannot be modified. Only the note "
                    "can be edited."))
        return super().write(vals)

    def unlink(self):
        if not self.env.su and not self.env.user.has_group(
                'sp_sale_price_history.group_price_history_manager'):
            raise UserError(_(
                "Only a Price History Manager can delete price history entries."))
        return super().unlink()

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    @api.model
    def get_dashboard_data(self, date_from=None, date_to=None):
        """KPI figures for the dashboard client action.

        Aggregation lives here rather than in JS so it can be tested without a
        browser. Scope is all time unless a range is passed; the front-end does
        not pass one today, which is a deliberate choice, not a limitation.
        """
        domain = []
        if date_from:
            domain.append(('change_date', '>=', date_from))
        if date_to:
            domain.append(('change_date', '<=', date_to))

        total = self.search_count(domain)
        grouped = self.read_group(domain, ['product_tmpl_id'], ['product_tmpl_id'])
        top = self.search(domain, order='price_diff desc', limit=1)
        bottom = self.search(domain, order='price_diff asc', limit=1)

        def describe(log):
            if not log or not log.price_diff:
                return {'amount': 0.0, 'product': '', 'currency': ''}
            return {
                'amount': log.price_diff,
                'product': log.product_tmpl_id.display_name,
                'currency': log.currency_id.symbol or log.currency_id.name,
            }

        return {
            'total_changes': total,
            'products_updated': len(grouped),
            'highest_increase': describe(top if top.price_diff > 0 else self.browse()),
            'highest_decrease': describe(bottom if bottom.price_diff < 0 else self.browse()),
        }

    @api.model
    def action_open_price_changes(self):
        action = self.env['ir.actions.act_window']._for_xml_id(
            'sp_sale_price_history.sp_price_history_log_action')
        return action
