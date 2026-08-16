# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SpIpAccessRuleHeader(models.Model):
    _name = 'sp.ip.access.rule.header'
    _description = "IP Access Rule Header Condition"
    _order = 'rule_id, id'

    rule_id = fields.Many2one(
        'sp.ip.access.rule', string="Rule", required=True, ondelete='cascade', index=True)
    header_key = fields.Char(
        string="Header", required=True,
        help="WSGI environment key, e.g. HTTP_HOST or HTTP_COOKIE.")
    header_value = fields.Char(
        string="Expected Value",
        help="Leave empty to require only that the header is present.")

    def _sp_clear_cache(self):
        self.env['sp.ip.access.rule']._sp_clear_cache()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self._sp_clear_cache()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._sp_clear_cache()
        return res

    def unlink(self):
        res = super().unlink()
        self._sp_clear_cache()
        return res
