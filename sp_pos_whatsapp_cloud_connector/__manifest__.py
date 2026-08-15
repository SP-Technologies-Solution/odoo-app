{
    "name": "SP POS WhatsApp Cloud Connector",
    "version": "18.0.1.0.0",
    "summary": "Send Point of Sale receipts to customers over WhatsApp",
    "description": """
WhatsApp Cloud API connector for Point of Sale
==============================================

Sends a POS receipt from Odoo to a customer on WhatsApp, as a PDF attachment.

* Point of Sale receipts, straight from the order form
* Respects the 24 hour customer service window: uses an approved template with a
  document header outside it, free-form inside it
* Message templates are synchronised from Meta, never hand-typed
* Delivery statuses (sent / delivered / read / failed) arrive over the webhook

Odoo ships no PDF report for an individual POS order, so this module adds one.
""",
    "author": "SP Technologies Solution",
    "website": "https://sptechnologiessolution.com/",
    "support": "contact@sptechnologiessolution.com",
    "maintainer": "SP Technologies Solution",
    "license": "LGPL-3",
    "category": "Productivity/Discuss",
    "price": 50.0,
    "currency": "USD",
    "images": ["static/description/banner.png"],
    "depends": [
        "base",
        "mail",
        "point_of_sale",
    ],
    "external_dependencies": {"python": ["phonenumbers", "requests"]},
    "data": [
        "security/whatsapp_security.xml",
        "security/ir.model.access.csv",
        "data/legal_params.xml",
        "report/pos_receipt_report.xml",
        "report/pos_receipt_templates.xml",
        "views/legal_templates.xml",
        # The template builder action is referenced from the account form,
        # so it has to be loaded first.
        "wizard/wa_template_builder_views.xml",
        "wizard/wa_send_wizard_views.xml",
        "views/wa_account_views.xml",
        "views/wa_template_views.xml",
        "views/wa_message_views.xml",
        "views/document_buttons.xml",
        "views/res_config_settings_views.xml",
        "views/wa_menus.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "sp_pos_whatsapp_cloud_connector/static/src/js/receipt_screen.js",
            "sp_pos_whatsapp_cloud_connector/static/src/xml/receipt_screen.xml",
        ],
    },
    "installable": True,
    "application": True,
}
