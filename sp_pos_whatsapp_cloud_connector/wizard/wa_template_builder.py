import re
from urllib.parse import urlparse

from odoo import _, api, fields, models
from odoo.exceptions import UserError


def _sample_pdf():
    """Build a minimal, structurally valid one-page PDF.

    Meta requires a sample asset for a media header and validates it, so the
    cross-reference table has to carry real byte offsets. Generating it here
    avoids shipping a binary file in the addon.
    """
    stream = b"BT /F1 18 Tf 60 780 Td (Sample document) Tj ET\n"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n%sendstream" % (len(stream), stream),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % index + body + b"\nendobj\n"

    xref_offset = len(out)
    size = len(objects) + 1
    out += b"xref\n0 %d\n" % size
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        size,
        xref_offset,
    )
    return bytes(out)


class WaTemplateBuilder(models.TransientModel):
    _name = "wa.template.builder"
    _description = "Create a WhatsApp Document Template"

    account_id = fields.Many2one(
        "wa.account",
        required=True,
        default=lambda self: self.env["wa.account"]._get_default_account(),
    )
    name = fields.Char(
        required=True,
        default="document_delivery",
        help="Lowercase letters, digits and underscores only.",
    )
    language_code = fields.Char(required=True, default="en")
    category = fields.Selection(
        [("UTILITY", "Utility"), ("MARKETING", "Marketing")],
        default="UTILITY",
        required=True,
        help="Invoices and receipts are Utility: cheaper and approved faster.",
    )
    body_text = fields.Text(
        required=True,
        default="Hi {{1}}, please find {{2}} attached.\n\n"
        "Amount due: {{3}}. Thank you for your business.",
        help="Use {{1}}, {{2}} ... for the values Odoo fills in at send time. "
        "The text may not begin or end with a variable.",
    )
    sample_values = fields.Char(
        required=True,
        default="Customer, POS/0001, 500.00",
        help="Comma separated example for each variable; Meta reviews these.",
    )
    footer_text = fields.Char(default=lambda self: self.env.company.name)

    add_link_button = fields.Boolean(
        string="Add portal link button",
        help="Adds a tappable button. Meta fixes the base URL at approval time and "
        "only accepts a dynamic suffix, so this locks the template to the host below.",
    )
    button_text = fields.Char(default="View Document")
    button_url_base = fields.Char(
        compute="_compute_button_url_base",
        store=True,
        readonly=False,
        help="Must match this database's web.base.url or links will break.",
    )

    @api.depends("add_link_button")
    def _compute_button_url_base(self):
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        for wizard in self:
            wizard.button_url_base = "%s/" % base.rstrip("/")

    @api.constrains("name")
    def _check_name(self):
        for wizard in self:
            if not re.fullmatch(r"[a-z0-9_]+", wizard.name or ""):
                raise UserError(
                    _("Template name must use only lowercase letters, digits and underscores.")
                )

    def _validate_body(self):
        """Apply Meta's formatting rules before spending an API call.

        Meta rejects "dangling parameters" with a bare code 100 / "Invalid
        parameter", which says nothing about the real cause, so catch them here.
        """
        self.ensure_one()
        body = (self.body_text or "").strip()
        if re.match(r"^{{\s*\d+\s*}}", body):
            raise UserError(
                _("The message body may not begin with a variable. Put some text first.")
            )
        if re.search(r"{{\s*\d+\s*}}$", body):
            raise UserError(
                _(
                    "The message body may not end with a variable — WhatsApp rejects "
                    "these as dangling parameters. Add text after the last variable, "
                    "for example 'Amount due: {{1}}. Thank you.'"
                )
            )
        if re.search(r"}}\s*{{", body):
            raise UserError(
                _("Two variables may not sit next to each other; separate them with text.")
            )

        numbers = sorted(int(n) for n in set(re.findall(r"{{\s*(\d+)\s*}}", body)))
        if numbers and numbers != list(range(1, len(numbers) + 1)):
            raise UserError(
                _("Variables must be numbered consecutively from {{1}}; found: %s.")
                % ", ".join("{{%d}}" % n for n in numbers)
            )
        return numbers

    def _components(self, header_handle):
        self.ensure_one()
        variables = len(self._validate_body())
        samples = [v.strip() for v in (self.sample_values or "").split(",") if v.strip()]
        if variables != len(samples):
            raise UserError(
                _(
                    "The body has %(vars)s variable(s) but %(samples)s sample value(s) "
                    "were given. Meta rejects templates whose examples do not line up."
                )
                % {"vars": variables, "samples": len(samples)}
            )

        components = [
            {
                "type": "HEADER",
                "format": "DOCUMENT",
                "example": {"header_handle": [header_handle]},
            }
        ]
        body = {"type": "BODY", "text": self.body_text}
        if samples:
            body["example"] = {"body_text": [samples]}
        components.append(body)

        if self.footer_text:
            components.append({"type": "FOOTER", "text": self.footer_text})

        if self.add_link_button:
            if not self.button_url_base:
                raise UserError(_("Set the button base URL."))
            # Meta fixes this base at approval time and will not let it be edited
            # afterwards, so a local address would permanently produce dead links.
            host = (urlparse(self.button_url_base).hostname or "").lower()
            if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1") or not host:
                raise UserError(
                    _(
                        "The button URL points at '%s', which no recipient's phone can "
                        "reach. Meta locks this address in at approval and it cannot be "
                        "changed later.\n\n"
                        "Set System Parameter 'web.base.url' to your public domain "
                        "first, or untick the link button to send the PDF only."
                    )
                    % (host or self.button_url_base)
                )
            components.append(
                {
                    "type": "BUTTONS",
                    "buttons": [
                        {
                            "type": "URL",
                            "text": self.button_text or "View Document",
                            "url": "%s{{1}}" % self.button_url_base,
                            "example": ["%smy/invoices/1?access_token=sample"
                                        % self.button_url_base],
                        }
                    ],
                }
            )
        return components

    def action_create_template(self):
        self.ensure_one()
        account = self.account_id
        handle = account.resumable_upload(
            _sample_pdf(), "sample.pdf", "application/pdf"
        )
        payload = {
            "name": self.name,
            "language": self.language_code,
            "category": self.category,
            "components": self._components(handle),
        }
        account.create_template(payload)
        # Pull it straight back so the new record carries Meta's own view of it.
        account._sync_templates()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "title": _("Template submitted"),
                "message": _(
                    "'%s' was sent to Meta for review. It usually takes under an hour; "
                    "press Sync Templates to refresh its status."
                )
                % self.name,
                "sticky": True,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
