# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError

SP_ACTIVITY_TYPE = 'sp_customer_invoice_approval.sp_mail_activity_type_invoice_approval'


class SpInvoiceRejectWizard(models.TransientModel):
    _name = 'sp.invoice.reject.wizard'
    _description = "Invoice Rejection Reason"

    move_id = fields.Many2one(
        'account.move', string="Invoice", required=True, ondelete='cascade')
    reason = fields.Text(string="Reason", required=True)

    def action_confirm(self):
        self.ensure_one()
        move = self.move_id
        move._sp_check_approver()
        if move.sp_approval_state != 'waiting':
            raise UserError(_("Only an invoice waiting for approval can be rejected."))
        move.write({
            'sp_approval_state': 'rejected',
            'sp_rejected_by': self.env.user.id,
            'sp_rejection_reason': self.reason,
            'sp_approved_by': False,
            'sp_approved_on': False,
        })
        move._sp_close_activities(_("Rejected by %s", self.env.user.display_name))
        move.message_post(body=_(
            "Invoice rejected by %(user)s.\nReason: %(reason)s",
            user=self.env.user.display_name, reason=self.reason))
        return {'type': 'ir.actions.act_window_close'}
