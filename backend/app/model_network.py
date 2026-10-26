"""User-controlled endpoints: validate at the actual connection, pin IP, preserve TLS SNI."""
import asyncio
import ipaddress
import re
import socket
import ssl
from urllib.parse import urlsplit
import httpcore
import httpx
from httpcore._backends.auto import AutoBackend
from .ai_service import ModelFailure


def unsafe():
    return ModelFailure('MODEL_URL_UNSAFE', '模型地址必须是公网 HTTPS/443 地址，不能访问本机、内网或元数据服务', 422)


def public_ip(value):
    try:
        ip = ipaddress.ip_address(value)
        # Explicitly exclude transition/mapped addresses whose embedded destination is ambiguous.
        if isinstance(ip, ipaddress.IPv6Address) and (ip in ipaddress.ip_network('64:ff9b::/96') or ip in ipaddress.ip_network('64:ff9b:1::/48')): return False
        return ip.is_global and not ip.is_multicast and not ip.is_reserved and not (isinstance(ip, ipaddress.IPv6Address) and (ip.ipv4_mapped or ip.sixtofour or ip.teredo))
    except ValueError: return False


def validate_base(value):
    if len(value) > 2048 or any(ord(c) < 33 for c in value) or any(c in value for c in ('\\', '%', '?', '#')):
        raise unsafe()
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or '').encode('idna').decode('ascii').lower()
        if parsed.scheme != 'https' or parsed.username is not None or parsed.password is not None or parsed.port not in (None, 443): raise ValueError()
        if not host or host.endswith('.') or any(label in ('',) for label in host.split('.')): raise ValueError()
        if not re.fullmatch(r'[A-Za-z0-9._:/-]*', parsed.path) or any(p in ('.','..') for p in parsed.path.split('/')): raise ValueError()
        try:
            ipaddress.ip_address(host)
            if not public_ip(host): raise ValueError()
        except ValueError:
            if ':' in host or not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{1,62}', host): raise unsafe()
            if host.endswith(('.localhost','.local','.internal','.lan','.home','.test','.invalid','.onion')): raise unsafe()
        authority = '['+host+']' if ':' in host else host
        return 'https://' + authority + parsed.path.rstrip('/')
    except (ValueError, UnicodeError): raise unsafe() from None


async def resolve_public(host, port):
    try:
        # All answers must be safe. Resolve only inside the bounded connect operation.
        answers = await asyncio.wait_for(asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM), timeout=5)
    except (OSError, asyncio.TimeoutError):
        raise ModelFailure('MODEL_UNAVAILABLE', '无法解析模型服务地址，请检查公网域名') from None
    addresses = list(dict.fromkeys(item[4][0] for item in answers))
    if not addresses or not all(public_ip(ip) for ip in addresses): raise unsafe()
    return addresses


class PublicNetworkBackend(AutoBackend):
    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        if port != 443: raise unsafe()
        async with asyncio.timeout(min(timeout or 5, 5)):
            addresses = await resolve_public(host, port)
            # Connect directly to a checked numerical IP; no second hostname lookup.
            # httpcore subsequently uses its ORIGINAL origin hostname for TLS SNI/certificate checks.
            return await super().connect_tcp(addresses[0], port, timeout=timeout, local_address=local_address, socket_options=socket_options)

    async def connect_unix_socket(self, *args, **kwargs): raise unsafe()


class PublicModelTransport(httpx.AsyncHTTPTransport):
    def __init__(self):
        # httpx 0.28/httpcore 1.x integration: use their HTTP mapping/stream lifecycle,
        # replace only pool construction to inject the validated network backend.
        self._pool = httpcore.AsyncConnectionPool(ssl_context=ssl.create_default_context(),
            max_connections=1, max_keepalive_connections=0, retries=0, network_backend=PublicNetworkBackend())
