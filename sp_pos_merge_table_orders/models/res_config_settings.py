from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_sp_merge_orders_enabled = fields.Boolean(
        related='pos_config_id.sp_merge_orders_enabled', readonly=False)
