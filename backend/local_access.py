"""Local-machine ingress boundary. No remote authentication or forwarded trust."""

import ipaddress
from urllib.parse import urlsplit

from starlette.responses import JSONResponse

from backend.compute_lease import local_engine


def loopback(value):
    if not isinstance(value, str):
        return False
    if value.lower() == 'localhost':
        return True
    try:
        address = ipaddress.ip_address(value)
        return address.is_loopback or bool(
            getattr(address, 'ipv4_mapped', None) and address.ipv4_mapped.is_loopback
        )
    except ValueError:
        return False


def origin(value):
    if not value or len(value) > 2048 or any(ord(c) <= 32 or ord(c) == 127 for c in value):
        raise ValueError('Invalid origin')
    parsed = urlsplit(value)
    if (
        parsed.scheme not in ('http', 'https')
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
        or not loopback(parsed.hostname)
    ):
        raise ValueError('Only a loopback origin is supported')
    if parsed.netloc.endswith(':') or '%' in parsed.hostname:
        raise ValueError('Invalid origin authority')
    port = parsed.port if parsed.port is not None else (443 if parsed.scheme == 'https' else 80)
    if not 1 <= port <= 65535:
        raise ValueError('Invalid origin port')
    return parsed.scheme, parsed.hostname.lower(), port


def allowed(scope, profile=None):
    peer = scope.get('client')
    if not peer or not (loopback(peer[0]) or profile is not None and profile.trusts(peer[0])):
        return False
    headers = {}
    for key, value in scope.get('headers', []):
        name = key.lower()
        if name in (b'host', b'origin', b'sec-fetch-site'):
            if name in headers:
                return False
            headers[name] = value.decode('latin-1')
    try:
        target = origin(
            scope.get('scheme', 'http').replace('ws', 'http') + '://' + headers.get(b'host', '')
        )
        if b'origin' in headers and origin(headers[b'origin']) != target:
            return False
    except (ValueError, TypeError):
        return False
    if headers.get(b'sec-fetch-site') == 'cross-site':
        # An external link may navigate to the local home page, but cannot read
        # APIs or perform writes. CLI requests do not carry browser fetch headers.
        raw = dict(scope.get('headers', []))
        return (
            scope.get('method') == 'GET'
            and not scope.get('path', '').startswith('/api')
            and raw.get(b'sec-fetch-mode') == b'navigate'
            and raw.get(b'sec-fetch-dest') == b'document'
        )
    return True


class LocalAccess:
    def __init__(self, app, profile):
        self.app = app
        self.profile = profile

    async def __call__(self, scope, receive, send):
        if scope['type'] not in ('http', 'websocket'):
            return await self.app(scope, receive, send)
        if not allowed(scope, self.profile):
            if scope['type'] == 'websocket':
                return await send(dict(type='websocket.close', code=1008))
            response = JSONResponse(
                status_code=403,
                content={'detail': '此平台僅供本機使用；請從同一台電腦的 localhost 網址開啟。'},
                headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'},
            )
            return await response(scope, receive, send)
        return await self.app(scope, receive, send)


def install(app, host):
    @app.get('/api/deployment')
    def deployment():
        engine = host.engine_url()
        return dict(
            schema_version=1,
            mode='container-local' if host.deployment.kind == 'container' else 'local-only',
            lan_enabled=False,
            public_access_enabled=False,
            authentication='none-local-machine-trust',
            ingress='loopback-host; explicit bridge peer; same-origin browser requests'
            if host.deployment.kind == 'container'
            else 'loopback-peer-and-host; same-origin browser requests',
            platform=dict(
                role='platform',
                source='container Python process'
                if host.deployment.kind == 'container'
                else 'platform Python process',
                runtime_kind=host.deployment.kind,
            ),
            engine=dict(
                url=engine,
                role='local-engine' if local_engine(engine) else 'external-engine',
                hardware_source='selected engine /system_stats; unknown if unavailable',
            ),
            storage=dict(role='platform-filesystem', path=str(host.DATA)),
            remote_browser_supported=False,
        )

    # Outermost middleware: rejected ingress cannot reach APIs or static files.
    app.add_middleware(LocalAccess, profile=host.deployment)
