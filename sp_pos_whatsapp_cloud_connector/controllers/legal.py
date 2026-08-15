from odoo import fields, http
from odoo.http import request

# System-parameter keys that let a deployer rebrand the legal pages without
# touching the code. The domain itself always comes from ``web.base.url``.
COMPANY_PARAM = "sp_pos_whatsapp_cloud_connector.legal_company_name"
EMAIL_PARAM = "sp_pos_whatsapp_cloud_connector.legal_contact_email"


class WhatsAppCloudLegal(http.Controller):
    """Publicly hosts the Privacy Policy, Terms of Service and Data Deletion
    pages that Meta requires for App Review. Serving them from the module keeps
    the URLs on the customer's own Odoo domain (read from ``web.base.url``)."""

    def _legal_context(self):
        params = request.env["ir.config_parameter"].sudo()
        base = params.get_param("web.base.url", "").rstrip("/")
        return {
            "company_name": params.get_param(COMPANY_PARAM) or "SP Technologies Solution",
            "contact_email": params.get_param(EMAIL_PARAM)
            or "contact@sptechnologiessolution.com",
            "base_url": base,
            "today": fields.Date.context_today(request.env.user).strftime("%d %B %Y"),
            "lang": request.env.lang or "en",
        }

    @http.route(
        "/whatsapp/cloud/privacy-policy",
        type="http",
        auth="public",
        website=False,
        sitemap=True,
    )
    def privacy_policy(self, **kw):
        return request.render(
            "sp_pos_whatsapp_cloud_connector.legal_privacy_policy", self._legal_context()
        )

    @http.route(
        "/whatsapp/cloud/terms-of-service",
        type="http",
        auth="public",
        website=False,
        sitemap=True,
    )
    def terms_of_service(self, **kw):
        return request.render(
            "sp_pos_whatsapp_cloud_connector.legal_terms_of_service", self._legal_context()
        )

    @http.route(
        "/whatsapp/cloud/data-deletion",
        type="http",
        auth="public",
        website=False,
        sitemap=True,
    )
    def data_deletion(self, **kw):
        return request.render(
            "sp_pos_whatsapp_cloud_connector.legal_data_deletion", self._legal_context()
        )
