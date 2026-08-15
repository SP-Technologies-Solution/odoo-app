import base64
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Meta caps a document caption at 1024 characters.
CAPTION_MAX = 1024


class WaMessage(models.Model):
    _name = "wa.message"
    _description = "WhatsApp Outbound Message"
    _order = "create_date desc, id desc"

    account_id = fields.Many2one("wa.account", required=True, ondelete="restrict")
    partner_id = fields.Many2one("res.partner", string="Recipient")
    phone = fields.Char(required=True, help="Recipient in E.164 digits, no plus sign.")

    model = fields.Char(index=True, help="Source document model.")
    res_id = fields.Many2oneReference(model_field="model", index=True)
    document_name = fields.Char(help="Human readable name of the source document.")

    template_id = fields.Many2one("wa.template", ondelete="restrict")
    body = fields.Text(help="Caption or free-form text actually sent.")
    portal_url = fields.Char()
    attachment_id = fields.Many2one("ir.attachment", ondelete="set null")
    media_id = fields.Char(readonly=True, copy=False, help="Meta media id, valid 30 days.")

    wamid = fields.Char("WhatsApp Message ID", readonly=True, copy=False, index=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("sent", "Sent"),
            ("delivered", "Delivered"),
            ("read", "Read"),
            ("failed", "Failed"),
        ],
        default="draft",
        readonly=True,
    )
    error_message = fields.Text(readonly=True)
    sent_date = fields.Datetime(readonly=True)

    @api.depends("document_name", "phone", "partner_id")
    def _compute_display_name(self):
        for message in self:
            target = message.partner_id.display_name or message.phone or ""
            message.display_name = "%s → %s" % (message.document_name or _("Message"), target)

    def action_open_document(self):
        self.ensure_one()
        if not (self.model and self.res_id):
            raise UserError(_("This message is not linked to a document."))
        return {
            "type": "ir.actions.act_window",
            "res_model": self.model,
            "res_id": self.res_id,
            "view_mode": "form",
        }

    # ------------------------------------------------------------------
    # Payload construction
    # ------------------------------------------------------------------
    def _base_payload(self):
        self.ensure_one()
        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self.phone,
        }

    def _caption(self):
        """Caption text, with the portal link appended when no button carries it."""
        self.ensure_one()
        caption = self.body or ""
        template = self.template_id
        appends_link = self.portal_url and (not template or template.link_mode == "none")
        if appends_link:
            caption = ("%s\n%s" % (caption, self.portal_url)).strip()
        return caption[:CAPTION_MAX]

    def _document_payload(self, media_id, filename):
        """Free-form document message. Only valid inside the 24h window."""
        payload = self._base_payload()
        document = {"id": media_id, "filename": filename}
        caption = self._caption()
        if caption:
            document["caption"] = caption
        payload.update({"type": "document", "document": document})
        return payload

    def _text_payload(self):
        payload = self._base_payload()
        payload.update(
            {"type": "text", "text": {"body": self._caption(), "preview_url": True}}
        )
        return payload

    def _template_payload(self, media_id=None, filename=None, body_params=None):
        """Template message, the only way to reach a closed 24h window."""
        self.ensure_one()
        template = self.template_id
        template._check_sendable()

        components = []
        if template.header_format == "DOCUMENT":
            # Meta requires the document header on every send of this template;
            # omitting it triggers "expected DOCUMENT, received UNKNOWN" (132012).
            if not media_id:
                raise UserError(
                    _(
                        "Template '%s' has a document header, so a PDF must be "
                        "attached. Choose a send mode that includes the PDF."
                    )
                    % template.name
                )
            components.append(
                {
                    "type": "header",
                    "parameters": [
                        {
                            "type": "document",
                            "document": {"id": media_id, "filename": filename},
                        }
                    ],
                }
            )

        params = list(body_params or [])
        if template.link_mode == "body" and self.portal_url:
            index = template.link_param_index
            if index and 1 <= index <= len(params) + 1:
                params.insert(index - 1, self.portal_url)
            else:
                params.append(self.portal_url)
        if params:
            components.append(
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": str(p)} for p in params],
                }
            )

        if template.link_mode == "button" and self.portal_url:
            # Meta only accepts the variable *suffix*; the base is fixed at
            # approval time. Strip the approved base off our absolute URL.
            suffix = self._url_button_suffix(template)
            components.append(
                {
                    "type": "button",
                    "sub_type": "url",
                    "index": "0",
                    "parameters": [{"type": "text", "text": suffix}],
                }
            )

        payload = self._base_payload()
        payload.update(
            {
                "type": "template",
                "template": {
                    "name": template.name,
                    "language": {"code": template.language_code},
                    "components": components,
                },
            }
        )
        return payload

    @staticmethod
    def _strip_scheme(url):
        """Drop http:// or https:// so the two can be compared interchangeably."""
        return re.sub(r"^https?://", "", (url or "").strip(), flags=re.IGNORECASE)

    def _url_button_suffix(self, template):
        """Return the part of the portal URL that follows the template's fixed base.

        Meta locks the scheme into the approved button, but web.base.url may
        legitimately move between http and https. Compare host+path only, so
        flipping the site to https does not silently break every link.
        """
        self.ensure_one()
        url = self.portal_url or ""
        base = (template.button_url_base or "").rstrip()
        bare_url = self._strip_scheme(url)
        bare_base = self._strip_scheme(base)
        if bare_base and bare_url.startswith(bare_base):
            return bare_url[len(bare_base):]
        # The template was approved against a different host than web.base.url.
        # Sending the whole URL would produce a broken double-prefixed link.
        raise UserError(
            _(
                "The portal link (%(url)s) does not start with the URL approved for "
                "template '%(template)s' (%(base)s). Either fix web.base.url or switch "
                "the template's link mode to 'Link inside the message body'."
            )
            % {"url": url, "template": template.name, "base": base or _("not set")}
        )

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------
    def _ensure_media(self):
        """Upload the attachment once and cache the media id on the record."""
        self.ensure_one()
        if self.media_id:
            return self.media_id
        if not self.attachment_id:
            return False
        attachment = self.attachment_id
        media_id = self.account_id.upload_media(
            base64.b64decode(attachment.datas),
            attachment.name,
            attachment.mimetype or "application/pdf",
        )
        self.media_id = media_id
        return media_id

    def send(self, use_template=None, body_params=None):
        """Send the message, choosing free-form or template automatically.

        `use_template=None` means: use a template when one is set, since that is
        the only form guaranteed to arrive outside the 24 hour customer service
        window.

        Errors are recorded on the record rather than raised: raising would roll
        the transaction back and discard both the failure state and the message
        itself, leaving no audit trail. Returns the messages that failed.
        """
        failed = self.browse()
        for message in self:
            try:
                media_id = message._ensure_media()
                filename = message.attachment_id.name or "document.pdf"
                wants_template = (
                    use_template if use_template is not None else bool(message.template_id)
                )
                if wants_template:
                    payload = message._template_payload(
                        media_id=media_id, filename=filename, body_params=body_params
                    )
                elif media_id:
                    payload = message._document_payload(media_id, filename)
                else:
                    payload = message._text_payload()

                wamid, _response = message.account_id.send_payload(payload)
                message.write(
                    {
                        "wamid": wamid,
                        "state": "sent",
                        "sent_date": fields.Datetime.now(),
                        "error_message": False,
                    }
                )
                message._log_on_document()
            except UserError as exc:
                _logger.warning("WhatsApp send failed for %s: %s", message.display_name, exc)
                message.write({"state": "failed", "error_message": str(exc)})
                failed |= message
        return failed

    def _log_on_document(self):
        """Leave a trace in the source document's chatter."""
        self.ensure_one()
        if not (self.model and self.res_id):
            return
        record = self.env[self.model].browse(self.res_id).exists()
        if not record or not hasattr(record, "message_post"):
            return
        record.message_post(
            body=_(
                "Sent on WhatsApp to %(target)s."
            )
            % {"target": self.partner_id.display_name or self.phone},
            attachment_ids=self.attachment_id.ids or None,
        )

    def action_resend(self):
        self.write({"state": "draft", "error_message": False})
        failed = self.send()
        return failed.notify_result() if failed else True

    def notify_result(self):
        """Surface the first failure to the user without losing the log record."""
        message = self[:1]
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "danger",
                "title": _("WhatsApp send failed"),
                "message": message.error_message or _("Unknown error"),
                "sticky": True,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
