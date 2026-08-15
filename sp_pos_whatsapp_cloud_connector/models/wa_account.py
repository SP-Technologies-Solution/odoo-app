import json
import logging
import secrets

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Meta retires a Graph API version roughly two years after release. v25.0
# (released 2026-02-18, supported until 2028-07-29) matches the version the
# webhook fields are subscribed at in the App Dashboard.
DEFAULT_API_VERSION = "v25.0"
DEFAULT_GRAPH_URL = "https://graph.facebook.com"
REQUEST_TIMEOUT = 30

# Codes worth translating into something an accountant can act on. Kept as plain
# source strings (not wrapped in _() here): calling _() at import time, before any
# language context exists, logs a "no translation language detected" warning. They
# are translated at lookup time instead, in _raise_for_meta_error.
# https://developers.facebook.com/docs/whatsapp/cloud-api/support/error-codes
FRIENDLY_ERRORS = {
    0: "The access token could not be authenticated. Generate a new token.",
    190: "The access token has expired. Generate a new one in Meta Business Settings.",
    131047: (
        "More than 24 hours have passed since this contact last messaged you, so a "
        "free-form message is not allowed. Send an approved template instead."
    ),
    131026: (
        "The message could not be delivered. The number may not be on WhatsApp, or the "
        "recipient has not accepted the latest WhatsApp Terms of Service."
    ),
    131051: "Unsupported message type.",
    132000: "The number of values supplied does not match the template's variables.",
    132001: "The template does not exist in that language, or it is not approved yet.",
    132012: "A template variable value does not match the format the template expects.",
    132015: "The template is paused because of low quality and cannot be used.",
    133010: "This phone number is not registered on the WhatsApp Business Platform.",
    130429: "WhatsApp throughput limit reached. Try again shortly.",
    80007: "The WhatsApp Business Account rate limit was hit. Try again later.",
}


class WaAccount(models.Model):
    _name = "wa.account"
    _description = "WhatsApp Cloud API Account"
    _inherit = ["mail.thread"]
    _order = "sequence, id"

    name = fields.Char(required=True, help="Label shown when picking a sending number.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )

    # --- Credentials, all taken from the Meta App Dashboard ------------------
    phone_number_id = fields.Char(
        "Phone Number ID",
        required=True,
        help="WhatsApp > API Setup > 'Phone number ID'. This is not the phone number.",
    )
    waba_id = fields.Char(
        "WhatsApp Business Account ID",
        help="Required to synchronise message templates from Meta.",
    )
    app_id = fields.Char(
        "Meta App ID",
        help="Only needed to create templates from Odoo: the Resumable Upload API "
        "that produces the header sample is scoped to the app, not the number.",
    )
    access_token = fields.Char(
        groups="sp_pos_whatsapp_cloud_connector.group_wa_manager",
        required=True,
        help="System User permanent token holding whatsapp_business_messaging and "
        "whatsapp_business_management permissions.",
    )
    api_version = fields.Char(default=DEFAULT_API_VERSION, required=True)
    graph_base_url = fields.Char(default=DEFAULT_GRAPH_URL, required=True)

    # --- Webhook -------------------------------------------------------------
    verify_token = fields.Char(
        groups="sp_pos_whatsapp_cloud_connector.group_wa_manager",
        copy=False,
        help="Paste this into Meta > WhatsApp > Configuration > Verify token.",
    )
    webhook_url = fields.Char(compute="_compute_webhook_url")

    # --- Meta App Review: public legal page URLs -----------------------------
    # Built from the ``web.base.url`` system parameter and served by the
    # module's own controller, so they live on this Odoo domain.
    privacy_policy_url = fields.Char(compute="_compute_legal_urls")
    terms_url = fields.Char(compute="_compute_legal_urls")
    data_deletion_url = fields.Char(compute="_compute_legal_urls")

    # --- Read back from Meta -------------------------------------------------
    display_phone_number = fields.Char(readonly=True)
    verified_name = fields.Char(readonly=True)
    quality_rating = fields.Char(readonly=True)

    template_ids = fields.One2many("wa.template", "account_id", string="Templates")
    default_template_id = fields.Many2one(
        "wa.template",
        string="Default Template",
        domain="[('account_id', '=', id), ('status', '=', 'APPROVED')]",
        help="Used when a document is sent outside the 24 hour customer service window.",
    )

    _sql_constraints = [
        (
            "phone_number_id_uniq",
            "unique(phone_number_id)",
            "A WhatsApp account already exists for this Phone Number ID.",
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("verify_token"):
                vals["verify_token"] = self._new_verify_token()
        return super().create(vals_list)

    @api.model
    def _new_verify_token(self):
        return secrets.token_urlsafe(24)

    def _compute_webhook_url(self):
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        for account in self:
            account.webhook_url = "%s/whatsapp/cloud/webhook" % base.rstrip("/")

    def _compute_legal_urls(self):
        base = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("web.base.url", "")
            .rstrip("/")
        )
        for account in self:
            account.privacy_policy_url = "%s/whatsapp/cloud/privacy-policy" % base
            account.terms_url = "%s/whatsapp/cloud/terms-of-service" % base
            account.data_deletion_url = "%s/whatsapp/cloud/data-deletion" % base

    def action_regenerate_verify_token(self):
        for account in self:
            account.verify_token = self._new_verify_token()
        return True

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------
    def _graph_url(self, path):
        self.ensure_one()
        return "%s/%s/%s" % (
            self.graph_base_url.rstrip("/"),
            self.api_version.strip("/"),
            str(path).lstrip("/"),
        )

    def _auth_headers(self):
        self.ensure_one()
        return {"Authorization": "Bearer %s" % self.sudo().access_token}

    def _raise_for_meta_error(self, response):
        """Turn a Meta error envelope into a readable UserError."""
        try:
            payload = response.json()
        except ValueError:
            raise UserError(
                _("WhatsApp returned an unreadable response (HTTP %(status)s):\n%(body)s")
                % {"status": response.status_code, "body": response.text[:500]}
            )
        error = payload.get("error") or {}
        code = error.get("code")

        # Code 100 is a catch-all: the actionable text lives in error_user_msg or
        # error_data.details, never in `message`. Surface every field Meta fills
        # in rather than a bare "Invalid parameter".
        error_data = error.get("error_data")
        if isinstance(error_data, str):
            # Meta sometimes returns error_data as a JSON-encoded string.
            try:
                error_data = json.loads(error_data)
            except ValueError:
                error_data = {"details": error_data}
        error_data = error_data or {}

        friendly = FRIENDLY_ERRORS.get(code)
        headline = (_(friendly) if friendly else False) or error.get("error_user_title")
        specifics = [
            error_data.get("details"),
            error.get("error_user_msg"),
            None if headline else error.get("message"),
        ]
        if not headline:
            headline = error.get("message") or _("Unknown error")

        lines = [headline]
        for item in specifics:
            if item and item not in lines:
                lines.append(item)

        trace = []
        if code is not None:
            trace.append("code %s" % code)
        if error.get("error_subcode"):
            trace.append("subcode %s" % error["error_subcode"])
        if error.get("type"):
            trace.append(error["type"])
        if error.get("fbtrace_id"):
            trace.append("fbtrace %s" % error["fbtrace_id"])

        _logger.warning(
            "WhatsApp API error on %s %s: %s",
            response.request.method if response.request else "?",
            response.url,
            json.dumps(error),
        )
        raise UserError(
            _("WhatsApp rejected the request.\n\n%(body)s\n\n(%(trace)s)")
            % {"body": "\n\n".join(lines), "trace": ", ".join(trace) or "no detail"}
        )

    def _call(self, method, path, **kwargs):
        """Perform an authenticated Graph API call and return the parsed body."""
        self.ensure_one()
        url = self._graph_url(path)
        headers = dict(self._auth_headers(), **kwargs.pop("headers", {}))
        try:
            response = requests.request(
                method, url, headers=headers, timeout=REQUEST_TIMEOUT, **kwargs
            )
        except requests.exceptions.Timeout:
            raise UserError(
                _("WhatsApp did not respond within %s seconds.") % REQUEST_TIMEOUT
            )
        except requests.exceptions.RequestException as exc:
            raise UserError(_("Could not reach WhatsApp: %s") % exc)

        if not response.ok:
            self._raise_for_meta_error(response)
        return response.json()

    # ------------------------------------------------------------------
    # High level API
    # ------------------------------------------------------------------
    def upload_media(self, content, filename, mimetype="application/pdf"):
        """Upload bytes to Meta and return the media id.

        Media uploaded this way stays available for 30 days, and documents may
        be up to 100 MB, so a rendered PDF never approaches the limit.
        """
        self.ensure_one()
        result = self._call(
            "POST",
            "%s/media" % self.phone_number_id,
            data={"messaging_product": "whatsapp", "type": mimetype},
            files={"file": (filename, content, mimetype)},
        )
        media_id = result.get("id")
        if not media_id:
            raise UserError(_("WhatsApp did not return a media id for %s.") % filename)
        return media_id

    def send_payload(self, payload):
        """POST a message payload, returning (wamid, raw_response)."""
        self.ensure_one()
        result = self._call(
            "POST",
            "%s/messages" % self.phone_number_id,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        messages = result.get("messages") or []
        wamid = messages[0].get("id") if messages else False
        return wamid, result

    def action_test_connection(self):
        """Fetch the phone number record so the user sees it really works."""
        self.ensure_one()
        result = self._call(
            "GET",
            self.phone_number_id,
            params={"fields": "display_phone_number,verified_name,quality_rating"},
        )
        self.write(
            {
                "display_phone_number": result.get("display_phone_number"),
                "verified_name": result.get("verified_name"),
                "quality_rating": result.get("quality_rating"),
            }
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "title": _("Connected"),
                "message": _("%(name)s (%(number)s) is reachable.")
                % {
                    "name": result.get("verified_name") or self.name,
                    "number": result.get("display_phone_number") or "",
                },
                "sticky": False,
            },
        }

    def resumable_upload(self, content, filename, mimetype="application/pdf"):
        """Upload a sample asset and return the handle a template header needs.

        This is the Resumable Upload API, not the media endpoint used for
        sending: it is scoped to the app and its second leg authenticates with
        `Authorization: OAuth <token>` rather than the usual Bearer scheme.
        """
        self.ensure_one()
        if not self.app_id:
            raise UserError(
                _("Set the Meta App ID on '%s' before creating templates.") % self.name
            )
        token = self.sudo().access_token

        session = self._call(
            "POST",
            "%s/uploads" % self.app_id,
            params={
                "file_name": filename,
                "file_length": len(content),
                "file_type": mimetype,
                "access_token": token,
            },
        )
        session_id = session.get("id")
        if not session_id:
            raise UserError(_("Meta did not return an upload session id."))

        url = self._graph_url(session_id)
        try:
            response = requests.post(
                url,
                headers={
                    "Authorization": "OAuth %s" % token,
                    "file_offset": "0",
                    "Content-Type": mimetype,
                },
                data=content,
                timeout=REQUEST_TIMEOUT,
            )
        except requests.exceptions.RequestException as exc:
            raise UserError(_("Could not upload the sample file: %s") % exc)
        if not response.ok:
            self._raise_for_meta_error(response)

        handle = response.json().get("h")
        if not handle:
            raise UserError(_("Meta did not return a file handle for the sample."))
        return handle

    def create_template(self, payload):
        """POST a template definition to Meta for review."""
        self.ensure_one()
        if not self.waba_id:
            raise UserError(
                _("Set the WhatsApp Business Account ID on '%s' first.") % self.name
            )
        return self._call(
            "POST",
            "%s/message_templates" % self.waba_id,
            json=payload,
            headers={"Content-Type": "application/json"},
        )

    def _sync_templates(self):
        """Pull the approved template list from Meta into wa.template."""
        self.ensure_one()
        if not self.waba_id:
            raise UserError(
                _(
                    "Set the WhatsApp Business Account ID on '%s' before "
                    "synchronising templates."
                )
                % self.name
            )
        Template = self.env["wa.template"]
        path = "%s/message_templates" % self.waba_id
        params = {"limit": 100, "fields": "id,name,language,status,category,components"}
        seen = Template.browse()
        while path:
            result = self._call("GET", path, params=params)
            for data in result.get("data") or []:
                seen |= Template._upsert_from_meta(self, data)
            # Cursor pagination: the next URL is absolute, so strip our prefix.
            next_url = ((result.get("paging") or {}).get("next")) or ""
            if not next_url:
                break
            path = next_url.split("/%s/" % self.api_version, 1)[-1]
            params = None

        # Templates that vanished from Meta (deleted, or belonging to a WABA this
        # account no longer points at) must not linger and look sendable.
        # Archive rather than unlink: wa.message.template_id is ondelete=restrict,
        # so sent history keeps its reference.
        stale = Template.search([("account_id", "=", self.id)]) - seen
        if stale:
            _logger.info(
                "Archiving %s WhatsApp template(s) no longer on WABA %s: %s",
                len(stale),
                self.waba_id,
                ", ".join(stale.mapped("name")),
            )
            stale.write({"active": False})

        _logger.info("Synced %s WhatsApp templates for %s", len(seen), self.name)
        return seen

    def action_sync_templates(self):
        for account in self:
            account._sync_templates()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "title": _("Templates synchronised"),
                "message": _("Templates were refreshed from Meta."),
                "sticky": False,
            },
        }

    @api.model
    def _get_default_account(self, company=None):
        company = company or self.env.company
        account = self.search([("company_id", "=", company.id)], limit=1) or self.search(
            [], limit=1
        )
        if not account:
            raise UserError(
                _(
                    "No WhatsApp account is configured. Create one under "
                    "WhatsApp > Configuration > Accounts."
                )
            )
        return account
