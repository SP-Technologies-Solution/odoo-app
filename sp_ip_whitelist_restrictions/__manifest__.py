# -*- coding: utf-8 -*-
{
    'name': 'SP IP Access Restrictions',
    'version': '18.0.1.0.0',
    'category': 'Extra Tools',
    'summary': 'Allow or deny requests to specific routes based on client IP, IP range, or CIDR network',
    'description': """
Define IP Access Rules that control which client addresses may reach which routes.

* Allow-only-listed or deny-listed, per rule.
* Route matching by exact path, prefix, or regular expression.
* IP entries as a single address, a network plus subnet mask, or CIDR notation;
  IPv4 and IPv6 both work.
* Optional comparison against the full URL rather than the path alone.
* Optional HTTP header conditions that must hold for the rule to apply.
* Rules are evaluated in sequence order and the first one that matches decides.
  A route no rule matches is left alone -- this is not a default-deny firewall.

Configure from Settings > Technical > IP Access Rules.
    """,
    'website': 'https://sptechnologiessolution.com/',
    'author': 'SP Technologies',
    'depends': ['mail', 'base_setup'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_config_parameter_data.xml',
        'views/sp_ip_access_rule_views.xml',
        'views/sp_ip_access_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
