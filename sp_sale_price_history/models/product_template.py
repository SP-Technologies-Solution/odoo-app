# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.tools import float_compare

from .sp_price_history_log import SP_LOGGING_KEY


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    sp_price_history_count = fields.Integer(
        string="Price Changes", compute='_compute_sp_price_history')
    sp_previous_price = fields.Float(
        string="Previous Price", compute='_compute_sp_price_history',
        digits='Product Price')
    sp_last_price_change = fields.Datetime(
        string="Last Price Change", compute='_compute_sp_price_history')

    def _compute_sp_price_history(self):
        """Read the log with sudo, scoped to the user's allowed companies.

        Sudo because someone allowed to edit a product is not necessarily
        allowed to read the audit log; the company filter keeps the multi-company
        boundary that the record rule would otherwise enforce.
        """
        Log = self.env['sp.price.history.log'].sudo()
        company_ids = self.env.companies.ids
        for template in self:
            domain = [
                ('product_tmpl_id', '=', template.id),
                ('company_id', 'in', company_ids),
            ]
            template.sp_price_history_count = Log.search_count(domain)
            last = Log.search(domain, order='change_date desc, id desc', limit=1)
            template.sp_previous_price = last.old_price if last else 0.0
            template.sp_last_price_change = last.change_date if last else False

    # ------------------------------------------------------------------
    # The logging hook
    # ------------------------------------------------------------------
    def write(self, vals):
        if 'list_price' not in vals:
            return super().write(vals)

        before = {template.id: template.list_price for template in self}
        res = super().write(vals)

        entries = []
        for template in self:
            old_price = before.get(template.id, 0.0)
            new_price = template.list_price
            # Compare on the currency's rounding, not with !=: a float write of
            # the same displayed price must not produce a history entry.
            rounding = template.currency_id.rounding or 0.01
            if float_compare(old_price, new_price, precision_rounding=rounding) == 0:
                continue
            entries.append({
                'product_tmpl_id': template.id,
                'product_id': template.product_variant_id.id or False,
                'currency_id': template.currency_id.id,
                'old_price': old_price,
                'new_price': new_price,
                'company_id': (template.company_id or self.env.company).id,
                'user_id': self.env.user.id,
            })

        if entries:
            self.env['sp.price.history.log'].sudo().with_context(
                **{SP_LOGGING_KEY: True}).create(entries)
        return res

    def action_sp_open_price_history(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Price History"),
            'res_model': 'sp.price.history.log',
            'view_mode': 'list,form',
            'domain': [('product_tmpl_id', '=', self.id)],
            'context': {'search_default_group_by_user': 0},
        }
