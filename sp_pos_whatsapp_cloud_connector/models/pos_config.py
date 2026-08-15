from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    wa_account_id = fields.Many2one(
        "wa.account",
        string="WhatsApp Account",
        help="Account used to send POS receipts on WhatsApp from this Point of Sale.",
    )
    wa_template_id = fields.Many2one(
        "wa.template",
        string="WhatsApp Receipt Template",
        domain="[('account_id', '=', wa_account_id), ('status', '=', 'APPROVED')]",
        help="Approved template used when a receipt is sent on WhatsApp from the "
        "payment screen. Leave empty to use the account's default template.",
    )
