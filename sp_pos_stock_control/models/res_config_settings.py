# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_sp_display_stock = fields.Boolean(
        related='pos_config_id.sp_display_stock', readonly=False)
    pos_sp_stock_display_type = fields.Selection(
        related='pos_config_id.sp_stock_display_type', readonly=False)
    pos_sp_out_of_stock_mode = fields.Selection(
        related='pos_config_id.sp_out_of_stock_mode', readonly=False)
