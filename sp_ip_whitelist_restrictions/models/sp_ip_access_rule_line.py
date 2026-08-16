# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .sp_ip_utils import parse_network


class SpIpAccessRuleLine(models.Model):
    _name = 'sp.ip.access.rule.line'
    _description = "IP Access Rule Entry"
    _order = 'rule_id, id'

    rule_id = fields.Many2one(
        'sp.ip.access.rule', string="Rule", required=True, ondelete='cascade', index=True)
    ip_value = fields.Char(
        string="IP / CIDR", required=True,
        help="A single address (10.0.0.4, 2001:db8::1) or CIDR notation "
             "(173.245.48.0/20). Leave the subnet mask empty when using CIDR.")
    subnet_mask = fields.Char(
        string="Subnet Mask",
        help="Optional, e.g. 255.255.255.0. Only for a bare network address; "
             "cannot be combined with CIDR notation.")

    @api.constrains('ip_value', 'subnet_mask')
    def _check_ip_value(self):
        """Reject bad entries on save rather than letting them never match."""
        for line in self:
            try:
                parse_network(line.ip_value, line.subnet_mask)
            except ValueError as error:
                raise ValidationError(_(
                    "%(value)s is not a valid IP address, network or CIDR range: "
                    "%(error)s", value=line.ip_value, error=error))

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
