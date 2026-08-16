# -*- coding: utf-8 -*-
from odoo import api, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields = super()._load_pos_data_fields(config_id)
        return fields + [
            field for field in ('qty_available', 'virtual_available')
            if field not in fields
        ]

    def _process_pos_ui_product_product(self, products, config_id):
        res = super()._process_pos_ui_product_product(products, config_id)
        # ``config_id`` is a pos.config recordset despite its name.
        config = config_id
        if not hasattr(config, '_sp_stock_enabled'):
            config = self.env['pos.config'].browse(config)
        if config._sp_stock_enabled():
            config._sp_apply_stock(products)
        return res
