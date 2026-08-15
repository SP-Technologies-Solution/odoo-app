import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Statuses Meta reports for a template. Only APPROVED may be sent; anything
# else comes back as error 132001.
TEMPLATE_STATUS = [
    ("APPROVED", "Approved"),
    ("PENDING", "In Review"),
    ("REJECTED", "Rejected"),
    ("PAUSED", "Paused"),
    ("DISABLED", "Disabled"),
]

HEADER_FORMAT = [
    ("NONE", "No Header"),
    ("TEXT", "Text"),
    ("DOCUMENT", "Document"),
    ("IMAGE", "Image"),
    ("VIDEO", "Video"),
]

LINK_MODE = [
    ("none", "Do not send a link"),
    ("button", "URL button"),
    ("body", "Link inside the message body"),
]


class WaTemplate(models.Model):
    _name = "wa.template"
    _description = "WhatsApp Message Template"
    _order = "name, language_code"

    name = fields.Char(
        required=True,
        help="Exact template name as approved by Meta (lowercase, underscores).",
    )
    account_id = fields.Many2one("wa.account", required=True, ondelete="cascade")
    language_code = fields.Char(default="en", required=True, help="For example en, en_US or hi.")
    category = fields.Selection(
        [("UTILITY", "Utility"), ("MARKETING", "Marketing"), ("AUTHENTICATION", "Authentication")],
        default="UTILITY",
    )
    status = fields.Selection(TEMPLATE_STATUS, default="PENDING", readonly=True)
    meta_template_id = fields.Char(readonly=True, copy=False)

    header_format = fields.Selection(HEADER_FORMAT, default="NONE", readonly=True)
    body_text = fields.Text(readonly=True, help="Body as approved by Meta, for reference.")
    body_param_count = fields.Integer(
        readonly=True, help="Number of {{n}} placeholders in the body."
    )

    # --- How the portal link is delivered ------------------------------------
    link_mode = fields.Selection(
        LINK_MODE,
        default="none",
        required=True,
        help="URL button: Meta only allows a dynamic suffix appended to a fixed base "
        "URL, so the base is locked in at template approval time. "
        "Body: the whole link is passed as a text variable, which survives a base "
        "URL change but looks less tidy.",
    )
    button_url_base = fields.Char(
        readonly=True,
        help="Fixed part of the URL button as approved by Meta.",
    )
    link_param_index = fields.Integer(
        string="Link Variable Position",
        default=0,
        help="When the link is sent in the body, which {{n}} placeholder holds it. "
        "0 means the link is appended to the caption instead.",
    )

    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "name_lang_account_uniq",
            "unique(name, language_code, account_id)",
            "This template already exists for that language and account.",
        ),
    ]

    @api.depends("name", "language_code", "status")
    def _compute_display_name(self):
        for template in self:
            label = "%s (%s)" % (template.name, template.language_code)
            if template.status != "APPROVED":
                label += " [%s]" % (template.status or "?")
            template.display_name = label

    def _check_sendable(self):
        """Guard before we spend an API call on a template Meta will refuse."""
        self.ensure_one()
        if self.status != "APPROVED":
            raise UserError(
                _(
                    "Template '%(name)s' is %(status)s, not approved. "
                    "WhatsApp only accepts approved templates."
                )
                % {"name": self.name, "status": self.status or _("unknown")}
            )
        return True

    # ------------------------------------------------------------------
    # Sync from Meta
    # ------------------------------------------------------------------
    def action_sync_from_meta(self):
        """Refresh from Meta: the selected templates' accounts, or every account."""
        accounts = self.mapped("account_id") or self.env["wa.account"].search([])
        return accounts.action_sync_templates()

    @api.model
    def _parse_components(self, components):
        """Flatten Meta's components array into our flat fields."""
        values = {
            "header_format": "NONE",
            "body_text": "",
            "body_param_count": 0,
            "button_url_base": False,
        }
        for component in components or []:
            ctype = (component.get("type") or "").upper()
            if ctype == "HEADER":
                values["header_format"] = (component.get("format") or "TEXT").upper()
            elif ctype == "BODY":
                body = component.get("text") or ""
                values["body_text"] = body
                # Positional placeholders look like {{1}}; count the distinct ones.
                values["body_param_count"] = len(
                    set(re.findall(r"{{\s*(\d+)\s*}}", body))
                )
            elif ctype == "BUTTONS":
                for button in component.get("buttons") or []:
                    if (button.get("type") or "").upper() == "URL":
                        url = button.get("url") or ""
                        # Meta stores the full pattern, e.g. https://host/{{1}}
                        values["button_url_base"] = url.split("{{")[0]
                        break
        return values

    def _upsert_from_meta(self, account, data):
        """Create or update one template record from a Meta payload."""
        values = self._parse_components(data.get("components"))
        values.update(
            {
                "name": data.get("name"),
                "account_id": account.id,
                "language_code": data.get("language") or "en",
                "category": (data.get("category") or "UTILITY").upper(),
                "status": (data.get("status") or "PENDING").upper(),
                "meta_template_id": data.get("id"),
            }
        )
        existing = self.with_context(active_test=False).search(
            [
                ("account_id", "=", account.id),
                ("name", "=", values["name"]),
                ("language_code", "=", values["language_code"]),
            ],
            limit=1,
        )
        if existing:
            # link_mode is a local choice, never overwrite it from Meta.
            existing.write(values)
            if values["button_url_base"] and existing.link_mode == "none":
                existing.link_mode = "button"
            return existing
        template = self.create(values)
        if values["button_url_base"]:
            template.link_mode = "button"
        return template
