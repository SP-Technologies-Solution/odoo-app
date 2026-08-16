# -*- coding: utf-8 -*-
import logging

from werkzeug.exceptions import Forbidden

from odoo import models
from odoo.http import request

from .sp_ip_utils import client_ip_from_chain, parse_networks

_logger = logging.getLogger(__name__)

SP_PARAM_TRUST_XFF = 'sp_ip_access.trust_forwarded_for'
SP_PARAM_TRUSTED_PROXIES = 'sp_ip_access.trusted_proxies'
SP_PARAM_FAIL_CLOSED = 'sp_ip_access.fail_closed'

_TRUE = ('1', 'True', 'true', 'yes')


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _pre_dispatch(cls, rule, args):
        # Checked before super() so a denied request does as little work as
        # possible; either way the controller has not run yet.
        request.env['ir.http']._sp_enforce_ip_access()
        return super()._pre_dispatch(rule, args)

    # ------------------------------------------------------------------
    # Client IP resolution
    # ------------------------------------------------------------------
    def _sp_client_ip(self):
        """The address to match rules against.

        By default this is the direct peer. X-Forwarded-For is honoured only
        when explicitly enabled *and* the direct peer is a configured trusted
        proxy -- otherwise anyone could set the header and pick their own IP.
        """
        httprequest = request.httprequest
        remote_addr = httprequest.remote_addr
        params = self.env['ir.config_parameter'].sudo()
        if params.get_param(SP_PARAM_TRUST_XFF, '0') not in _TRUE:
            return remote_addr
        trusted = parse_networks(params.get_param(SP_PARAM_TRUSTED_PROXIES, ''))
        return client_ip_from_chain(
            remote_addr, httprequest.headers.get('X-Forwarded-For'), trusted)

    # ------------------------------------------------------------------
    # Enforcement
    # ------------------------------------------------------------------
    def _sp_enforce_ip_access(self):
        try:
            verdict = self._sp_ip_access_verdict()
        except Forbidden:
            raise
        except Exception:
            # A malformed rule must not take every route down. Fail open by
            # default, loudly; flip SP_PARAM_FAIL_CLOSED to invert that.
            _logger.exception("IP access check failed; letting the request through")
            if self._sp_fail_closed():
                raise Forbidden("Access check failed.")
            return
        if verdict is None or verdict['allowed']:
            return
        _logger.info(
            "IP access rule %s (%s) denied %s for %s",
            verdict['rule']['id'], verdict['rule']['name'],
            self._sp_client_ip(), request.httprequest.path)
        raise Forbidden("Your address is not allowed to access this resource.")

    def _sp_fail_closed(self):
        try:
            params = self.env['ir.config_parameter'].sudo()
            return params.get_param(SP_PARAM_FAIL_CLOSED, '0') in _TRUE
        except Exception:
            return False

    def _sp_ip_access_verdict(self):
        rules = self.env['sp.ip.access.rule'].sudo()
        if not rules._sp_compiled_rules():
            return None
        httprequest = request.httprequest
        return rules._sp_evaluate(
            httprequest.path,
            httprequest.base_url,
            self._sp_client_ip(),
            httprequest.environ,
        )
