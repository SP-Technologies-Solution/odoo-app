# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

# Only customer documents go through approval, matching the scope of the brief.
SP_APPROVAL_MOVE_TYPES = ('out_invoice', 'out_refund')

SP_ACTIVITY_TYPE = 'sp_customer_invoice_approval.sp_mail_activity_type_invoice_approval'


class AccountMove(models.Model):
    _inherit = 'account.move'

    sp_approval_state = fields.Selection(
        selection=[
            ('draft', "To Submit"),
            ('waiting', "Waiting for Approval"),
            ('approved', "Approved"),
            ('rejected', "Rejected"),
        ],
        string="Approval", default='draft', copy=False, readonly=True,
        tracking=True,
        help="Approval stage of this invoice. Independent from the accounting "
             "state so the native posting flow is gated, never replaced.")
    sp_approved_by = fields.Many2one('res.users', string="Approved by", readonly=True, copy=False)
    sp_approved_on = fields.Datetime(string="Approved on", readonly=True, copy=False)
    sp_rejected_by = fields.Many2one('res.users', string="Rejected by", readonly=True, copy=False)
    sp_rejection_reason = fields.Text(string="Rejection Reason", readonly=True, copy=False)

    sp_approval_required = fields.Boolean(compute='_compute_sp_approval_required')
    sp_is_approver = fields.Boolean(compute='_compute_sp_is_approver')

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('move_type', 'company_id')
    def _compute_sp_approval_required(self):
        for move in self:
            move.sp_approval_required = move._sp_needs_approval()

    @api.depends('company_id')
    def _compute_sp_is_approver(self):
        for move in self:
            approvers = move.company_id.sudo().sp_invoice_approver_ids
            move.sp_is_approver = self.env.user in approvers

    @api.depends('sp_approval_state')
    def _compute_hide_post_button(self):
        """Hide the native Post/Confirm button until the invoice is approved.

        Extending the existing compute keeps us out of the native buttons'
        ``invisible`` expressions, which differ between series.
        """
        super()._compute_hide_post_button()
        for move in self:
            if move._sp_needs_approval() and move.sp_approval_state != 'approved':
                move.hide_post_button = True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _sp_needs_approval(self):
        """True when this move is in scope and its company has approvers."""
        self.ensure_one()
        if self.move_type not in SP_APPROVAL_MOVE_TYPES:
            return False
        return bool(self.company_id.sudo().sp_invoice_approver_ids)

    def _sp_check_approver(self):
        """Guard the approve/reject entry points server-side."""
        if self.env.su:
            return
        for move in self:
            approvers = move.company_id.sudo().sp_invoice_approver_ids
            if self.env.user not in approvers:
                raise AccessError(_(
                    "Only an Invoice Approver of %s can approve or reject this "
                    "invoice.", move.company_id.display_name))

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_sp_send_for_approval(self):
        for move in self:
            if not move._sp_needs_approval():
                raise UserError(_(
                    "No Invoice Approver is configured for %s.",
                    move.company_id.display_name))
            if move.state != 'draft':
                raise UserError(_("Only a draft invoice can be sent for approval."))
            if move.sp_approval_state == 'waiting':
                raise UserError(_("This invoice is already waiting for approval."))
            move.write({
                'sp_approval_state': 'waiting',
                'sp_rejection_reason': False,
                'sp_rejected_by': False,
            })
            note = _(
                "Invoice for %s is waiting for your approval.",
                move.partner_id.display_name or _("this customer"))
            for approver in move.company_id.sudo().sp_invoice_approver_ids:
                move.activity_schedule(SP_ACTIVITY_TYPE, user_id=approver.id, note=note)
        return True

    def action_sp_approve(self):
        self._sp_check_approver()
        for move in self:
            if move.sp_approval_state != 'waiting':
                raise UserError(_("Only an invoice waiting for approval can be approved."))
            move.write({
                'sp_approval_state': 'approved',
                'sp_approved_by': self.env.user.id,
                'sp_approved_on': fields.Datetime.now(),
            })
            move._sp_close_activities(_("Approved by %s", self.env.user.display_name))
            move.message_post(body=_("Invoice approved by %s.", self.env.user.display_name))
        return True

    def action_sp_open_reject_wizard(self):
        self.ensure_one()
        self._sp_check_approver()
        if self.sp_approval_state != 'waiting':
            raise UserError(_("Only an invoice waiting for approval can be rejected."))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Reject Invoice"),
            'res_model': 'sp.invoice.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_move_id': self.id},
        }

    def action_sp_reset_approval(self):
        """Send a rejected invoice back to the submitter."""
        for move in self:
            if move.sp_approval_state != 'rejected':
                raise UserError(_("Only a rejected invoice can be reset."))
            move.write({
                'sp_approval_state': 'draft',
                'sp_rejection_reason': False,
                'sp_rejected_by': False,
            })
        return True

    def _sp_close_activities(self, feedback):
        self.activity_feedback([SP_ACTIVITY_TYPE], feedback=feedback)

    # ------------------------------------------------------------------
    # Native flow hooks
    # ------------------------------------------------------------------
    def action_post(self):
        """A hidden button is not a blocked action -- refuse it here too."""
        for move in self:
            if move._sp_needs_approval() and move.sp_approval_state != 'approved':
                raise UserError(_(
                    "Invoice %s must be approved before it can be posted.",
                    move.display_name))
        res = super().action_post()
        self._sp_notify_customers()
        return res

    def button_draft(self):
        res = super().button_draft()
        for move in self:
            if move._sp_needs_approval():
                move.write({
                    'sp_approval_state': 'draft',
                    'sp_approved_by': False,
                    'sp_approved_on': False,
                })
        return res

    def _sp_notify_customers(self):
        """Mail the customer once the approved invoice is actually posted.

        Sent on posting rather than on approval on purpose: a draft invoice has
        no number yet, so a mail sent at approval time would reference nothing
        the customer can act on.
        """
        template = self.env.ref(
            'sp_customer_invoice_approval.sp_mail_template_invoice_approved',
            raise_if_not_found=False)
        if not template:
            return
        for move in self:
            if move.state != 'posted' or not move._sp_needs_approval():
                continue
            if move.sp_approval_state != 'approved':
                continue
            if not move.company_id.sudo().sp_notify_customer_on_approval:
                continue
            if not move.partner_id.email:
                continue
            template.sudo().send_mail(move.id, force_send=False)
