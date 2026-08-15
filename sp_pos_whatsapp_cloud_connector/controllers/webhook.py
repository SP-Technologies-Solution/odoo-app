import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# Meta status values map straight onto wa.message states.
STATUS_MAP = {
    "sent": "sent",
    "delivered": "delivered",
    "read": "read",
    "failed": "failed",
}

# Never move a message backwards: a late 'sent' must not overwrite 'read'.
STATUS_RANK = {"draft": 0, "sent": 1, "delivered": 2, "read": 3, "failed": 3}


class WhatsAppCloudWebhook(http.Controller):
    @http.route(
        "/whatsapp/cloud/webhook",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        save_session=False,
    )
    def verify(self, **kw):
        """Meta's subscription handshake: echo hub.challenge when the token matches."""
        mode = kw.get("hub.mode")
        token = kw.get("hub.verify_token")
        challenge = kw.get("hub.challenge")
        if mode != "subscribe" or not token or not challenge:
            return request.make_response("Forbidden", status=403)

        account = (
            request.env["wa.account"]
            .sudo()
            .search([("verify_token", "=", token)], limit=1)
        )
        if not account:
            _logger.warning("WhatsApp webhook verification failed: unknown verify token.")
            return request.make_response("Forbidden", status=403)

        return request.make_response(
            challenge, headers=[("Content-Type", "text/plain")]
        )

    @http.route(
        "/whatsapp/cloud/webhook",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def notify(self, **kw):
        """Consume status callbacks and update the matching wa.message records."""
        try:
            payload = json.loads(request.httprequest.data.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            _logger.warning("WhatsApp webhook received an unparseable body.")
            # Always 200, or Meta retries and eventually disables the webhook.
            return request.make_response("EVENT_RECEIVED", status=200)

        try:
            self._handle_payload(payload)
        except Exception:  # noqa: BLE001 - never let Meta see a 500
            _logger.exception("Error while handling a WhatsApp webhook payload.")

        return request.make_response("EVENT_RECEIVED", status=200)

    def _handle_payload(self, payload):
        Message = request.env["wa.message"].sudo()
        for entry in payload.get("entry") or []:
            for change in entry.get("changes") or []:
                value = change.get("value") or {}
                for status in value.get("statuses") or []:
                    self._apply_status(Message, status)

    def _apply_status(self, Message, status):
        wamid = status.get("id")
        new_state = STATUS_MAP.get(status.get("status"))
        if not (wamid and new_state):
            return

        message = Message.search([("wamid", "=", wamid)], limit=1)
        if not message:
            return
        if STATUS_RANK.get(new_state, 0) <= STATUS_RANK.get(message.state, 0):
            return

        values = {"state": new_state}
        if new_state == "failed":
            errors = status.get("errors") or []
            if errors:
                error = errors[0]
                values["error_message"] = "[%s] %s - %s" % (
                    error.get("code"),
                    error.get("title") or "",
                    (error.get("error_data") or {}).get("details")
                    or error.get("message")
                    or "",
                )
        message.write(values)
