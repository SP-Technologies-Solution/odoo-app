from odoo import fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    # Stored fields on pos.config are sent to the POS front-end automatically
    # (the config is loaded with all of its fields), so no _load_pos_data_fields
    # override is needed to expose this to `pos.config.sp_merge_orders_enabled`.
    sp_merge_orders_enabled = fields.Boolean(
        string="Enable Order Merging",
        help="Let cashiers combine several open table orders on the same floor "
             "into one order, directly from the Point of Sale screen.")
