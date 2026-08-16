# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models, tools
from odoo.exceptions import ValidationError
from odoo.http import request

from .sp_ip_utils import (
    compile_route,
    headers_match,
    ip_in_networks,
    parse_network,
    route_matches,
)

_logger = logging.getLogger(__name__)

# Locking yourself out of these is not a recoverable mistake from the UI.
SP_SENSITIVE_ROUTES = ('/web', '/web/login', '/odoo', '/web/session/authenticate')

SP_PARAM_ALLOW_LOCKOUT = 'sp_ip_access.allow_lockout'


class SpIpAccessRule(models.Model):
    _name = 'sp.ip.access.rule'
    _description = "IP Access Rule"
    _inherit = ['mail.thread']
    _order = 'sequence, id'

    name = fields.Char(string="Description", required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    sequence = fields.Integer(
        default=10,
        help="Rules are evaluated low to high. The first rule whose route and "
             "header conditions match decides the request; no later rule is "
             "consulted.")
    route = fields.Char(
        required=True, tracking=True,
        help="Path to protect, e.g. /web/database. Compared against the URL "
             "path, or against the full URL when Compare Full URL is set.")
    route_match_type = fields.Selection(
        selection=[
            ('exact', "Exact Match"),
            ('prefix', "Prefix"),
            ('regex', "Regular Expression"),
        ],
        string="Route Matching", default='prefix', required=True, tracking=True,
        help="Regular expressions are applied with a search, so an unanchored "
             "pattern may match anywhere. Use ^ to anchor at the start.")
    match_full_url = fields.Boolean(
        string="Compare Full URL", tracking=True,
        help="Compare against scheme://host/path instead of the path alone, so "
             "a rule can distinguish sub-domains.")
    restriction_method = fields.Selection(
        selection=[
            ('allow_listed', "Allow Only Listed IPs"),
            ('deny_listed', "Deny Listed IPs"),
        ],
        default='allow_listed', required=True, tracking=True)

    ip_line_ids = fields.One2many(
        'sp.ip.access.rule.line', 'rule_id', string="IP List", copy=True)
    header_line_ids = fields.One2many(
        'sp.ip.access.rule.header', 'rule_id', string="Header Conditions", copy=True)

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('restriction_method', 'ip_line_ids')
    def _check_allow_list_not_empty(self):
        for rule in self:
            if rule.restriction_method == 'allow_listed' and not rule.ip_line_ids:
                raise ValidationError(_(
                    "Rule '%s' allows only listed IPs but lists none, which "
                    "would deny every request to that route.", rule.name))

    @api.constrains('route', 'route_match_type')
    def _check_route_compiles(self):
        for rule in self:
            if rule.route_match_type != 'regex':
                continue
            try:
                compile_route(rule.route, 'regex')
            except Exception as error:
                raise ValidationError(_(
                    "Rule '%(name)s' has an invalid regular expression: %(error)s",
                    name=rule.name, error=error))

    @api.constrains('route', 'route_match_type', 'restriction_method',
                    'ip_line_ids', 'active')
    def _check_self_lockout(self):
        """Refuse a rule that would lock the current admin out of the backend.

        Only meaningful when a real request is in flight; a rule created from a
        cron or `odoo shell` has no IP to compare against.
        """
        if not request:
            return
        params = self.env['ir.config_parameter'].sudo()
        if params.get_param(SP_PARAM_ALLOW_LOCKOUT, '0') in ('1', 'True', 'true'):
            return
        try:
            client_ip = self.env['ir.http']._sp_client_ip()
        except Exception:  # pragma: no cover - never block a save on this
            _logger.warning("Could not resolve the client IP for the lockout check")
            return
        for rule in self:
            if not rule.active or rule.restriction_method != 'allow_listed':
                continue
            if not rule._sp_covers_sensitive_route():
                continue
            if ip_in_networks(client_ip, rule._sp_networks()):
                continue
            raise ValidationError(_(
                "Rule '%(name)s' would lock you out: it allows only listed IPs "
                "on a backend route, and your address %(ip)s is not listed.\n"
                "Add your address, or set the system parameter %(param)s to 1 "
                "if you really mean it.",
                name=rule.name, ip=client_ip, param=SP_PARAM_ALLOW_LOCKOUT))

    def _sp_covers_sensitive_route(self):
        self.ensure_one()
        compiled = compile_route(self.route, self.route_match_type)
        return any(
            route_matches(sensitive, self.route, self.route_match_type, compiled)
            for sensitive in SP_SENSITIVE_ROUTES
        )

    def _sp_networks(self):
        self.ensure_one()
        networks = []
        for line in self.ip_line_ids:
            try:
                networks.append(parse_network(line.ip_value, line.subnet_mask))
            except ValueError:
                continue
        return networks

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------
    def _sp_clear_cache(self):
        registry = self.env.registry
        if hasattr(registry, 'clear_cache'):
            registry.clear_cache()
        else:  # Odoo 16 and earlier
            self.clear_caches()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self._sp_clear_cache()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._sp_clear_cache()
        return res

    def unlink(self):
        res = super().unlink()
        self._sp_clear_cache()
        return res

    # ------------------------------------------------------------------
    # Compiled form consumed by the dispatch hook
    # ------------------------------------------------------------------
    @api.model
    @tools.ormcache()
    def _sp_compiled_rules(self):
        """All active rules, pre-parsed, in evaluation order.

        Runs once per registry until a rule changes; the dispatch hook must not
        issue a query per request.
        """
        compiled = []
        for rule in self.sudo().search([]):
            try:
                compiled.append({
                    'id': rule.id,
                    'name': rule.name,
                    'route': rule.route,
                    'match_type': rule.route_match_type,
                    'full_url': rule.match_full_url,
                    'method': rule.restriction_method,
                    'pattern': compile_route(rule.route, rule.route_match_type),
                    'networks': rule._sp_networks(),
                    'headers': [
                        (line.header_key, line.header_value or None)
                        for line in rule.header_line_ids
                    ],
                })
            except Exception:
                # One broken rule must not take the whole site down.
                _logger.exception("Skipping unparseable IP access rule %s", rule.id)
        return tuple(compiled)

    @api.model
    def _sp_evaluate(self, path, full_url, client_ip, environ):
        """First matching rule decides. ``None`` means no rule applied."""
        for rule in self._sp_compiled_rules():
            target = full_url if rule['full_url'] else path
            if not route_matches(target, rule['route'], rule['match_type'], rule['pattern']):
                continue
            if rule['headers'] and not headers_match(environ, rule['headers']):
                # Header conditions gate whether the rule applies at all, so a
                # mismatch falls through to the next rule.
                continue
            listed = ip_in_networks(client_ip, rule['networks'])
            allowed = listed if rule['method'] == 'allow_listed' else not listed
            return {'rule': rule, 'allowed': allowed}
        return None
