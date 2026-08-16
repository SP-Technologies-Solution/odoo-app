# -*- coding: utf-8 -*-
"""Route and IP matching helpers.

Deliberately free of Odoo imports so the matching logic can be exercised on its
own, which matters here: this code runs on every single HTTP request.
"""
import ipaddress
import re

ROUTE_MATCH_EXACT = 'exact'
ROUTE_MATCH_PREFIX = 'prefix'
ROUTE_MATCH_REGEX = 'regex'


def parse_network(ip_value, subnet_mask=None):
    """Normalise the three accepted input styles into one ip_network.

    Accepts a bare address ("10.0.0.4", "2001:db8::1"), CIDR notation
    ("173.245.48.0/20"), or a network address plus a dotted subnet mask
    ("192.168.1.0" + "255.255.255.0"). Raises ValueError on anything else.
    """
    value = (ip_value or '').strip()
    if not value:
        raise ValueError("Empty IP value")

    mask = (subnet_mask or '').strip()
    if mask:
        if '/' in value:
            raise ValueError(
                "Give either CIDR notation or a subnet mask, not both: %s / %s"
                % (value, mask))
        return ipaddress.ip_network("%s/%s" % (value, mask), strict=False)

    # A bare address becomes a single-host network, so containment is one code
    # path for every entry.
    return ipaddress.ip_network(value, strict=False)


def ip_in_networks(ip_value, networks):
    """True when ``ip_value`` falls inside any of ``networks``."""
    if not ip_value or not networks:
        return False
    try:
        address = ipaddress.ip_address(ip_value.strip())
    except ValueError:
        return False
    for network in networks:
        # An IPv4 address is never inside an IPv6 network; skip rather than raise.
        if address.version != network.version:
            continue
        if address in network:
            return True
    return False


def parse_networks(raw, separator=','):
    """Parse a separated list of IP/CIDR values, skipping anything unparseable."""
    networks = []
    for chunk in (raw or '').split(separator):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            networks.append(parse_network(chunk))
        except ValueError:
            continue
    return networks


def compile_route(route, match_type):
    """Pre-compile the regex for regex rules; None for the other match types."""
    if match_type == ROUTE_MATCH_REGEX:
        return re.compile(route or '')
    return None


def route_matches(target, route, match_type, compiled=None):
    """Does ``target`` (a path, or a full URL) match this rule's route?

    Regex rules use ``re.search``, so an unanchored pattern matches anywhere in
    the target and ``^`` anchors it explicitly. This is documented behaviour --
    ``re.match`` would silently anchor every pattern.
    """
    if not target:
        return False
    if match_type == ROUTE_MATCH_EXACT:
        return target == route
    if match_type == ROUTE_MATCH_PREFIX:
        return target.startswith(route or '')
    if match_type == ROUTE_MATCH_REGEX:
        pattern = compiled or re.compile(route or '')
        return bool(pattern.search(target))
    return False


def headers_match(environ, conditions):
    """All header conditions must hold.

    ``conditions`` is a list of ``(key, expected_or_None)``. A ``None``/empty
    expected value means "the header must merely be present".
    """
    for key, expected in conditions:
        if key not in environ:
            return False
        if expected and environ.get(key) != expected:
            return False
    return True


def client_ip_from_chain(remote_addr, forwarded_for, trusted_networks):
    """Resolve the real client IP behind a chain of trusted proxies.

    Walks ``X-Forwarded-For`` right to left and returns the first hop that is
    not itself a trusted proxy. Returns ``remote_addr`` unchanged when the
    direct peer is not a trusted proxy, so a forged header from an untrusted
    source buys the sender nothing.
    """
    if not trusted_networks or not ip_in_networks(remote_addr, trusted_networks):
        return remote_addr
    hops = [hop.strip() for hop in (forwarded_for or '').split(',') if hop.strip()]
    for hop in reversed(hops):
        if not ip_in_networks(hop, trusted_networks):
            return hop
    return remote_addr
