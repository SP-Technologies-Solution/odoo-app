# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sp_invoice_approver_ids = fields.Many2many(
        related='company_id.sp_invoice_approver_ids', readonly=False)
    sp_notify_customer_on_approval = fields.Boolean(
        related='company_id.sp_notify_customer_on_approval', readonly=False)
