# -*- coding: utf-8 -*-
{
    'name': 'SP Customer Invoice Approval',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Require approver sign-off before customer invoices can be posted',
    'description': """
Adds an approval step in front of the customer invoice posting flow.

* List the Invoice Approvers per company under Invoicing > Configuration > Settings.
* An accountant sends a draft invoice for approval; every approver gets a
  scheduled activity on the invoice.
* Any one approver can Approve or Reject. Rejection asks for a reason and
  records it on the invoice and in the chatter.
* Until the invoice is approved the Confirm button is hidden and the server
  refuses to post it, so the rule holds for direct RPC calls too.
* Optionally e-mail the customer once the approved invoice has been posted.
    """,
    'website': 'https://sptechnologiessolution.com/',
    'author': 'SP Technologies Solution',
    'images': ['static/description/banner.png'],
    'price': 12.0,
    'currency': 'USD',
    'depends': ['account', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/mail_activity_type_data.xml',
        'data/mail_template_data.xml',
        'wizard/sp_invoice_reject_wizard_views.xml',
        'views/account_move_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
