# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    sp_invoice_approver_ids = fields.Many2many(
        'res.users', 'sp_invoice_approver_company_rel', 'company_id', 'user_id',
        string="Invoice Approvers", domain=[('share', '=', False)],
        help="Users allowed to approve or reject customer invoices of this "
             "company. Leaving this empty switches the workflow off.")
    sp_notify_customer_on_approval = fields.Boolean(
        string="Notify Customer",
        help="Send the customer an e-mail once an approved invoice is posted.")
