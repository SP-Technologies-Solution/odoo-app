from odoo import _, models
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def sp_log_merge(self, source_labels):
        """Record on the destination order's chatter which orders were merged.

        Called from the POS front-end once the line consolidation has been
        synced. ``source_labels`` is the list of human-readable names/tables of
        the orders that were folded in. Author and timestamp are added by
        ``message_post`` automatically.
        """
        if not source_labels:
            return False
        labels = ", ".join(source_labels)
        body = _("Merged the following order(s) into this one: %s.", labels)
        for order in self:
            order.message_post(body=body)
        return True

    def _sp_assert_mergeable(self):
        """Server-side guard mirroring the front-end checks.

        Kept authoritative so a merge that reaches the server can still be
        refused if a payment slipped in from another terminal.
        """
        for order in self:
            if order.state != 'draft':
                raise UserError(_(
                    "Order %s can no longer be merged because it is not a "
                    "draft order.", order.pos_reference or order.name))
            if order.payment_ids:
                raise UserError(_(
                    "Order %s already has a payment in progress and cannot be "
                    "merged.", order.pos_reference or order.name))
        return True
