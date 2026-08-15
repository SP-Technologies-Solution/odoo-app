from odoo import _, models
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _name = "pos.order"
    _inherit = ["pos.order", "wa.send.mixin"]

    def _wa_report_ref(self):
        # Odoo core ships no PDF report for an individual pos.order, only
        # report_userlabel and the session-level report_saledetails, so this
        # module adds its own receipt layout.
        return "sp_pos_whatsapp_cloud_connector.action_report_pos_receipt"

    def _wa_partner(self):
        self.ensure_one()
        return self.partner_id

    def _wa_document_name(self):
        self.ensure_one()
        return self.pos_reference or self.name

    # ------------------------------------------------------------------
    # One-click send from the POS receipt screen
    # ------------------------------------------------------------------
    def action_send_whatsapp_receipt(self, phone=False):
        """Called from the POS receipt screen. Sends the receipt PDF on
        WhatsApp using the account/template configured on the POS."""
        for order in self:
            order._send_whatsapp_receipt(phone=phone)
        return True

    def _send_whatsapp_receipt(self, phone=False):
        self.ensure_one()
        config = self.config_id
        account = (config and config.wa_account_id) or self.env[
            "wa.account"
        ]._get_default_account(self.company_id)
        if not account:
            raise UserError(
                _(
                    "No WhatsApp account is configured. Set one in "
                    "Point of Sale → Settings → WhatsApp."
                )
            )
        template = (config and config.wa_template_id) or account.default_template_id

        partner = self.partner_id
        raw = phone or (
            getattr(partner, "mobile", False)
            or (partner.phone if partner else False)
        )
        to = self._wa_normalise_phone(raw, partner.country_id if partner else None)
        if not to:
            raise UserError(
                _(
                    "No WhatsApp number found for this order. Add a customer with a "
                    "phone number, or set the customer's number before sending."
                )
            )

        attachment = self._wa_render_attachment()
        message = self.env["wa.message"].create(
            {
                "account_id": account.id,
                "partner_id": partner.id if partner else False,
                "phone": to,
                "model": self._name,
                "res_id": self.id,
                "document_name": self._wa_document_name(),
                "template_id": template.id if template else False,
                "attachment_id": attachment.id,
            }
        )
        body_params = []
        if template:
            body_params = self._wa_default_params()[: template.body_param_count or 0]
        failed = message.send(use_template=bool(template), body_params=body_params)
        if failed:
            raise UserError(message.error_message or _("WhatsApp send failed."))
        return True
