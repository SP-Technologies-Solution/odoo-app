from odoo import _, api, fields, models
from odoo.exceptions import UserError

MAX_BODY_PARAMS = 5


class WaSendWizard(models.TransientModel):
    _name = "wa.send.wizard"
    _description = "Send Document on WhatsApp"

    model = fields.Char(required=True)
    res_id = fields.Integer(required=True)
    document_name = fields.Char(readonly=True)

    account_id = fields.Many2one(
        "wa.account",
        required=True,
        default=lambda self: self.env["wa.account"]._get_default_account(),
    )
    partner_id = fields.Many2one("res.partner", string="Recipient")
    phone = fields.Char(
        required=True, help="E.164 digits without a plus sign, e.g. 919876543210."
    )

    send_mode = fields.Selection(
        [
            ("pdf", "Receipt PDF"),
            ("text", "Message only (no attachment)"),
        ],
        default="pdf",
        required=True,
        help="Receipt PDF sends the receipt as a document. Message only sends "
        "just the text, e.g. a review or thank-you message.",
    )
    portal_url = fields.Char(readonly=True)
    portal_available = fields.Boolean(readonly=True)

    use_template = fields.Boolean(
        default=True,
        help="Required unless the contact messaged you within the last 24 hours. "
        "Outside that window WhatsApp rejects free-form messages with error 131047.",
    )
    template_id = fields.Many2one(
        "wa.template",
        domain="[('account_id', '=', account_id), ('status', '=', 'APPROVED')]",
    )
    template_body = fields.Text(related="template_id.body_text", readonly=True)
    body_param_count = fields.Integer(related="template_id.body_param_count", readonly=True)
    template_link_mode = fields.Selection(related="template_id.link_mode", readonly=True)

    param_1 = fields.Char("Variable 1")
    param_2 = fields.Char("Variable 2")
    param_3 = fields.Char("Variable 3")
    param_4 = fields.Char("Variable 4")
    param_5 = fields.Char("Variable 5")

    caption = fields.Text(
        help="Used as the document caption for free-form messages. Templates use "
        "their approved body instead."
    )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        model = values.get("model") or self.env.context.get("default_model")
        res_id = values.get("res_id") or self.env.context.get("default_res_id")
        if not (model and res_id):
            return values

        record = self.env[model].browse(res_id)
        partner = record._wa_partner()
        portal_url = record._wa_portal_url()
        account = self.env["wa.account"]._get_default_account(
            record.company_id if "company_id" in record._fields else None
        )
        values.update(
            {
                "document_name": record._wa_document_name(),
                "partner_id": partner.id,
                "phone": record._wa_normalise_phone(
                    getattr(partner, "mobile", False) or partner.phone,
                    partner.country_id,
                ),
                "portal_url": portal_url,
                "portal_available": bool(portal_url),
                "account_id": account.id,
                "template_id": account.default_template_id.id,
                "caption": _("%(document)s from %(company)s")
                % {
                    "document": record._wa_document_name(),
                    "company": self.env.company.name,
                },
            }
        )
        # Prefill the template variables so the user is not staring at blanks.
        for index, value in enumerate(record._wa_default_params()[:MAX_BODY_PARAMS], 1):
            values.setdefault("param_%d" % index, value)

        values["send_mode"] = "pdf"
        return values

    @api.onchange("template_id")
    def _onchange_template_id(self):
        """A document-header template must carry the PDF; a message-only send
        would drop the mandatory header and Meta rejects it (error 132012)."""
        template = self.template_id
        if template and template.header_format == "DOCUMENT" and self.send_mode == "text":
            self.send_mode = "pdf"

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if self.partner_id:
            self.phone = self.env["wa.send.mixin"]._wa_normalise_phone(
                getattr(self.partner_id, "mobile", False) or self.partner_id.phone,
                self.partner_id.country_id,
            )

    def _body_params(self):
        self.ensure_one()
        params = [
            self[f"param_{index}"] for index in range(1, MAX_BODY_PARAMS + 1)
        ]
        expected = self.template_id.body_param_count or 0
        # The link occupies one body slot when the template carries it inline.
        if self.template_id.link_mode == "body":
            expected = max(expected - 1, 0)
        return [p or "" for p in params[:expected]]

    def action_send(self):
        self.ensure_one()
        if not self.phone:
            raise UserError(
                _("No WhatsApp number for %s. Set a mobile number on the contact.")
                % (self.partner_id.display_name or _("the recipient"))
            )
        if self.use_template and not self.template_id:
            raise UserError(
                _(
                    "Pick an approved template, or untick 'Use template' if this "
                    "contact messaged you within the last 24 hours."
                )
            )

        record = self.env[self.model].browse(self.res_id)
        # A document-header template needs its PDF on every send, whatever the
        # chosen mode: dropping it makes Meta reject the whole message (132012).
        needs_document = (
            self.use_template and self.template_id.header_format == "DOCUMENT"
        )
        if self.send_mode == "text" and needs_document:
            raise UserError(
                _(
                    "Template '%s' has a document header, so it always sends the "
                    "receipt PDF. For a message-only send, choose a plain-text "
                    "template (no document header) or untick 'Use template'."
                )
                % self.template_id.name
            )
        # A URL-button template needs a link value that a POS order can't provide.
        if self.use_template and self.template_id.link_mode == "button":
            raise UserError(
                _(
                    "Template '%s' has a URL button, which POS orders can't fill. "
                    "Choose a template without a URL button."
                )
                % self.template_id.name
            )

        wants_pdf = self.send_mode == "pdf" or needs_document
        if wants_pdf and self.use_template and self.template_id.header_format != "DOCUMENT":
            raise UserError(
                _(
                    "Template '%s' has no document header, so it cannot carry the "
                    "PDF. Choose a template with a document header, or switch the "
                    "send mode to 'Message only'."
                )
                % self.template_id.name
            )

        attachment = record._wa_render_attachment() if wants_pdf else False
        message = self.env["wa.message"].create(
            {
                "account_id": self.account_id.id,
                "partner_id": self.partner_id.id,
                "phone": self.phone,
                "model": self.model,
                "res_id": self.res_id,
                "document_name": self.document_name,
                "template_id": self.template_id.id if self.use_template else False,
                "body": self.caption,
                "portal_url": False,
                "attachment_id": attachment.id if attachment else False,
            }
        )
        failed = message.send(
            use_template=self.use_template, body_params=self._body_params()
        )
        if failed:
            return failed.notify_result()
        return {"type": "ir.actions.act_window_close"}
