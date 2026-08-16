# -*- coding: utf-8 -*-
import base64
import io

from odoo import _, fields, models
from odoo.exceptions import UserError

try:
    import xlsxwriter
except ImportError:  # pragma: no cover - depends on the host environment
    xlsxwriter = None


class SpPriceHistoryExportWizard(models.TransientModel):
    _name = 'sp.price.history.export.wizard'
    _description = "Export Price History"

    date_from = fields.Date(string="From", required=True)
    date_to = fields.Date(string="To", required=True, default=fields.Date.context_today)
    product_ids = fields.Many2many(
        'product.template', string="Products",
        help="Leave empty to export every product.")
    export_format = fields.Selection(
        selection=[('pdf', "PDF"), ('xlsx', "XLSX")],
        string="Format", default='pdf', required=True)

    def _check_range(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError(_("The start date must not be after the end date."))

    def _get_domain(self):
        self.ensure_one()
        domain = [
            ('change_date', '>=', fields.Datetime.to_datetime(self.date_from)),
            ('change_date', '<=', fields.Datetime.to_datetime(self.date_to).replace(
                hour=23, minute=59, second=59)),
        ]
        if self.product_ids:
            domain.append(('product_tmpl_id', 'in', self.product_ids.ids))
        return domain

    def get_lines(self):
        """Log entries in the selected range. Public: the QWeb report calls it."""
        self.ensure_one()
        return self.env['sp.price.history.log'].search(
            self._get_domain(), order='change_date asc, id asc')

    def action_export(self):
        self.ensure_one()
        self._check_range()
        if self.export_format == 'pdf':
            report = self.env.ref(
                'sp_sale_price_history.sp_price_history_report_action')
            return report.report_action(self)
        return self._export_xlsx()

    def _export_xlsx(self):
        if xlsxwriter is None:
            raise UserError(_(
                "The xlsxwriter Python package is required for XLSX export. "
                "Install it, or export to PDF instead."))
        lines = self.get_lines()

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet(_("Price History"))

        header = workbook.add_format({'bold': True, 'bg_color': '#DDDDDD', 'border': 1})
        date_fmt = workbook.add_format({'num_format': 'yyyy-mm-dd hh:mm'})
        money = workbook.add_format({'num_format': '#,##0.00'})
        percent = workbook.add_format({'num_format': '0.00"%"'})

        columns = [
            (_("Change Date"), 18), (_("Product"), 38), (_("Old Price"), 14),
            (_("New Price"), 14), (_("Difference"), 14), (_("Change (%)"), 12),
            (_("Changed By"), 20), (_("Company"), 22),
        ]
        for index, (label, width) in enumerate(columns):
            sheet.write(0, index, label, header)
            sheet.set_column(index, index, width)
        sheet.freeze_panes(1, 0)

        for row, line in enumerate(lines, start=1):
            # Excel has no timezone, so write the user's local wall clock.
            local_date = fields.Datetime.context_timestamp(self, line.change_date)
            sheet.write_datetime(row, 0, local_date.replace(tzinfo=None), date_fmt)
            sheet.write_string(row, 1, line.product_tmpl_id.display_name or '')
            sheet.write_number(row, 2, line.old_price, money)
            sheet.write_number(row, 3, line.new_price, money)
            sheet.write_number(row, 4, line.price_diff, money)
            sheet.write_number(row, 5, line.price_diff_percent, percent)
            sheet.write_string(row, 6, line.user_id.display_name or '')
            sheet.write_string(row, 7, line.company_id.display_name or '')

        workbook.close()
        payload = output.getvalue()
        output.close()

        attachment = self.env['ir.attachment'].create({
            'name': 'price_history_%s_%s.xlsx' % (self.date_from, self.date_to),
            'type': 'binary',
            'datas': base64.b64encode(payload),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.'
                        'spreadsheetml.sheet',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }
