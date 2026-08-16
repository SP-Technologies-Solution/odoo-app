# -*- coding: utf-8 -*-
from odoo import fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    sp_display_stock = fields.Boolean(
        string="Show Stock on Products",
        help="Display the available quantity on every product card of the POS "
             "product grid. Only storable products get a quantity.")
    sp_stock_display_type = fields.Selection(
        selection=[
            ('on_hand', "On Hand"),
            ('forecasted', "Forecasted"),
            ('both', "On Hand + Forecasted"),
        ],
        string="Quantity Shown", default='on_hand', required=True,
        help="Which quantity is shown on the product card. The same quantity "
             "drives the out-of-stock check, except for On Hand + Forecasted "
             "where On Hand is used.")
    sp_out_of_stock_mode = fields.Selection(
        selection=[
            ('off', "No Restriction"),
            ('warn', "Warn & Confirm"),
            ('block', "Block Sale"),
        ],
        string="Out-of-Stock Products", default='off', required=True,
        help="What happens when a cashier adds a storable product whose "
             "available quantity is already exhausted by the current order:\n"
             "- No Restriction: nothing, the stock figure stays informative.\n"
             "- Warn & Confirm: a dialog asks to confirm before adding.\n"
             "- Block Sale: the product is refused.")

    def _sp_stock_context(self):
        """Context in which product quantities are evaluated for this POS.

        Falls back to an empty context (company-wide quantities) when the
        operation type has no source location.
        """
        self.ensure_one()
        location = self.picking_type_id.default_location_src_id
        return {'location': location.id} if location else {}

    def _sp_stock_enabled(self):
        self.ensure_one()
        return self.sp_display_stock or self.sp_out_of_stock_mode != 'off'

    def _sp_apply_stock(self, products, model='product.product'):
        """Re-read the POS-local quantities into already-read product dicts.

        ``products`` is the list of dicts sent to the POS front-end; it is
        updated in place.
        """
        self.ensure_one()
        context = self._sp_stock_context()
        if not context or not products:
            return
        records = self.env[model].with_context(**context).browse(
            [p['id'] for p in products])
        quantities = {
            vals['id']: vals
            for vals in records.read(['qty_available', 'virtual_available'])
        }
        for product in products:
            vals = quantities.get(product['id'])
            if vals:
                product['qty_available'] = vals['qty_available']
                product['virtual_available'] = vals['virtual_available']
