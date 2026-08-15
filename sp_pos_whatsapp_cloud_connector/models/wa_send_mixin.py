import base64
import logging
import re

from odoo import _, api, fields, models
from odoo.tools.misc import formatLang

_logger = logging.getLogger(__name__)

try:
    import phonenumbers
except ImportError:  # pragma: no cover - optional at import time
    phonenumbers = None
    _logger.warning("phonenumbers is not installed; WhatsApp numbers get a naive cleanup.")


class WaSendMixin(models.AbstractModel):
    """Adds 'Send on WhatsApp' to any document that can be rendered as a PDF.

    Concrete models override `_wa_report_ref` and, when they have a portal page,
    inherit the default `_wa_portal_url` behaviour.
    """

    _name = "wa.send.mixin"
    _description = "WhatsApp Send Mixin"

    wa_message_ids = fields.One2many(
        "wa.message",
        "res_id",
        domain=lambda self: [("model", "=", self._name)],
        string="WhatsApp Messages",
    )
    wa_message_count = fields.Integer(compute="_compute_wa_message_count")

    @api.depends("wa_message_ids")
    def _compute_wa_message_count(self):
        if not self.ids:
            self.wa_message_count = 0
            return
        grouped = self.env["wa.message"]._read_group(
            [("model", "=", self._name), ("res_id", "in", self.ids)],
            groupby=["res_id"],
            aggregates=["__count"],
        )
        counts = {res_id: count for res_id, count in grouped}
        for record in self:
            record.wa_message_count = counts.get(record.id, 0)

    # ------------------------------------------------------------------
    # To be specialised per model
    # ------------------------------------------------------------------
    def _wa_report_ref(self):
        """XML id of the ir.actions.report producing this document's PDF."""
        raise NotImplementedError(
            _("No WhatsApp report is configured for %s.") % self._name
        )

    def _wa_partner(self):
        """Default recipient."""
        self.ensure_one()
        return self.partner_id if "partner_id" in self._fields else self.env["res.partner"]

    def _wa_document_name(self):
        self.ensure_one()
        return self.display_name

    def _wa_filename(self):
        """A tidy filename; WhatsApp shows this under the document bubble."""
        self.ensure_one()
        safe = re.sub(r"[^A-Za-z0-9._-]+", "-", self._wa_document_name() or "document")
        return "%s.pdf" % safe.strip("-")

    def _wa_default_params(self):
        """Sensible prefill for a template's {{1}}, {{2}}, {{3}} ...

        Ordered to match the shape most document templates take: who it is for,
        what it is, and how much. Trimmed or padded by the wizard to the number
        the chosen template actually declares.
        """
        self.ensure_one()
        partner = self._wa_partner()
        values = [partner.name or "", self._wa_document_name() or ""]
        if "amount_total" in self._fields:
            currency = self.currency_id if "currency_id" in self._fields else None
            values.append(formatLang(self.env, self.amount_total, currency_obj=currency))
        return values

    def _wa_portal_url(self):
        """Absolute portal URL with an access token, or False when unavailable.

        `_get_share_url` returns a *relative* path, so the base URL has to be
        prepended or the link arrives broken.
        """
        self.ensure_one()
        if not hasattr(self, "_portal_ensure_token"):
            return False
        access_url = self.access_url if "access_url" in self._fields else False
        if not access_url or access_url == "#":
            return False
        self._portal_ensure_token()
        return "%s%s" % (self.get_base_url(), self.get_portal_url())

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @api.model
    def _wa_normalise_phone(self, number, country=None):
        """Return E.164 digits with no plus sign, as the Cloud API expects."""
        if not number:
            return False
        raw = number.strip()
        if phonenumbers:
            try:
                region = country.code if country else None
                parsed = phonenumbers.parse(raw, region)
                if phonenumbers.is_valid_number(parsed):
                    formatted = phonenumbers.format_number(
                        parsed, phonenumbers.PhoneNumberFormat.E164
                    )
                    return formatted.lstrip("+")
            except phonenumbers.NumberParseException:
                pass
        digits = re.sub(r"\D", "", raw)
        return digits or False

    def _wa_render_attachment(self):
        """Render the document's PDF and store it as an attachment."""
        self.ensure_one()
        report_ref = self._wa_report_ref()
        pdf_content, _content_type = self.env["ir.actions.report"]._render_qweb_pdf(
            report_ref, self.ids
        )
        return self.env["ir.attachment"].create(
            {
                "name": self._wa_filename(),
                "type": "binary",
                "datas": base64.b64encode(pdf_content),
                "res_model": self._name,
                "res_id": self.id,
                "mimetype": "application/pdf",
            }
        )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_send_whatsapp(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Send on WhatsApp"),
            "res_model": "wa.send.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_model": self._name,
                "default_res_id": self.id,
            },
        }

    def action_open_wa_messages(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("WhatsApp Messages"),
            "res_model": "wa.message",
            "view_mode": "list,form",
            "domain": [("model", "=", self._name), ("res_id", "=", self.id)],
        }
