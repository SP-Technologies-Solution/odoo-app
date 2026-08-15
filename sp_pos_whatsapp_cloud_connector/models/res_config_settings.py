from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_wa_account_id = fields.Many2one(
        related="pos_config_id.wa_account_id", readonly=False
    )
    pos_wa_template_id = fields.Many2one(
        related="pos_config_id.wa_template_id", readonly=False
    )
