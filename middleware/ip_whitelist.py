import ipaddress
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Always allowed, regardless of conf file
ALWAYS_ALLOWED = {
    ipaddress.ip_address("127.0.0.1"),
    ipaddress.ip_address("::1"),
}


def _load_networks(conf_path: Path):
    networks = []
    try:
        with open(conf_path) as f:
            for line in f:
                line = line.split("#")[0].strip()
                if not line:
                    continue
                try:
                    networks.append(ipaddress.ip_network(line, strict=False))
                except ValueError:
                    logger.warning("ip_whitelist: invalid entry ignored: %r", line)
    except FileNotFoundError:
        logger.warning("ip_whitelist: conf file not found: %s — allowing only localhost", conf_path)
    return networks


def _parse_client_ip(environ):
    """Extract the real client IP from the WSGI environ."""
    # Honour X-Forwarded-For only if explicitly trusted (not here — raw socket IP)
    raw = environ.get("REMOTE_ADDR", "")
    try:
        addr = ipaddress.ip_address(raw)
        # Unwrap IPv4-mapped IPv6 (::ffff:x.x.x.x)
        if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
            addr = addr.ipv4_mapped
        return addr
    except ValueError:
        return None


class SilentDropMiddleware:
    """
    WSGI middleware that drops connections from non-whitelisted IPs without
    sending any HTTP response.  start_response is never called; returning an
    empty iterator causes Werkzeug / gunicorn to close the socket silently.
    """

    def __init__(self, app, conf_path: Path):
        self.app = app
        self.conf_path = conf_path

    def _is_allowed(self, addr):
        if addr is None:
            return False
        if addr in ALWAYS_ALLOWED:
            return True
        networks = _load_networks(self.conf_path)
        return any(addr in net for net in networks)

    def __call__(self, environ, start_response):
        addr = _parse_client_ip(environ)
        if not self._is_allowed(addr):
            logger.info("ip_whitelist: blocked %s", addr)
            # Return empty iterator WITHOUT calling start_response → silent drop
            return iter([])
        return self.app(environ, start_response)
