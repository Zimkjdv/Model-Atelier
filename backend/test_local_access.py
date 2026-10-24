import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend import local_access, main


class LocalAccessTests(TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.app = main.create_app(data_root=Path(temporary.name))
        self.app.state.context.initialize()

    def client(self, *, peer='127.0.0.1', url='http://127.0.0.1:8000'):
        result = TestClient(self.app, base_url=url, client=(peer, 12345))
        self.addCleanup(result.close)
        return result

    def test_loopback_http_clients_and_matching_browser_origins(self):
        for peer, url in [
            ('127.0.0.1', 'http://127.0.0.1:8000'),
            ('::1', 'http://localhost:8000'),
            ('::ffff:127.0.0.1', 'http://localhost:8000'),
        ]:
            client = self.client(peer=peer, url=url)
            self.assertEqual(client.get('/api/health').status_code, 200)
            self.assertEqual(
                client.put(
                    '/api/settings',
                    json={'comfy_url': 'http://127.0.0.1:8188'},
                    headers={'Origin': url},
                ).status_code,
                200,
            )
        self.assertEqual(
            self.client()
            .get('/api/health', headers={'Host': '[::1]:8000', 'Origin': 'http://[::1]:8000'})
            .status_code,
            200,
        )

    def test_rebound_hosts_invalid_origins_and_cross_site_requests_never_reach_api(self):
        client = self.client()
        original = client.get('/api/settings').json()
        for headers in [
            {'Host': 'attacker.invalid'},
            {'Host': 'localhost:0'},
            {'Host': 'localhost:'},
            {'Origin': 'null'},
            {'Origin': 'http://127.0.0.1:8001'},
            {'Origin': 'http://user@127.0.0.1:8000'},
            {'Origin': 'http://127.0.0.1:8000/'},
            {'Origin': 'http://127.0.0.1:8000?q=1'},
            {'Origin': 'http://127.0.0.1:8000#fragment'},
            {'Origin': 'https://attacker.invalid'},
            {'Sec-Fetch-Site': 'cross-site'},
        ]:
            with self.subTest(headers=headers):
                response = client.put(
                    '/api/settings', json={'comfy_url': 'http://127.0.0.1:9999'}, headers=headers
                )
                self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(client.get('/api/settings').json(), original)

    def test_remote_peers_cannot_spoof_local_forwarding_headers(self):
        for peer in ('192.168.1.2', '172.17.0.2', '8.8.8.8'):
            response = self.client(peer=peer).get(
                '/api/health',
                headers={
                    'X-Forwarded-For': '127.0.0.1',
                    'Forwarded': 'for=127.0.0.1;host=localhost',
                },
            )
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.headers['cache-control'], 'no-store')

    def test_duplicate_authority_or_origin_headers_are_rejected(self):
        client = self.client()
        for headers in [
            [('Host', '127.0.0.1:8000'), ('Host', 'attacker.invalid')],
            [('Origin', 'http://127.0.0.1:8000'), ('Origin', 'https://attacker.invalid')],
        ]:
            self.assertEqual(client.get('/api/health', headers=headers).status_code, 403)

    def test_report_separates_browser_boundary_from_outbound_engine(self):
        client = self.client()
        before = client.get('/api/settings').json()
        with patch('backend.main.httpx.AsyncClient', side_effect=AssertionError('read only')):
            report = client.get('/api/deployment').json()
        self.assertEqual(report['mode'], 'local-only')
        self.assertFalse(report['lan_enabled'])
        self.assertEqual(report['engine']['role'], 'local-engine')
        client.put('/api/settings', json={'comfy_url': 'https://engine.invalid'})
        report = client.get('/api/deployment').json()
        self.assertEqual(report['engine']['role'], 'external-engine')
        self.assertEqual(report['platform']['source'], 'platform Python process')
        self.assertNotEqual(before['comfy_url'], report['engine']['url'])
        self.assertEqual(report['storage']['path'], str(self.app.state.context.DATA))

    def test_external_navigation_to_home_does_not_allow_api_reads(self):
        self.app.get('/boundary-home')(lambda: {'view': 'local'})
        self.app.routes.insert(0, self.app.routes.pop())
        client = self.client()
        headers = {
            'Sec-Fetch-Site': 'cross-site',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Dest': 'document',
        }
        self.assertEqual(client.get('/api/health', headers=headers).status_code, 403)
        self.assertEqual(client.get('/boundary-home', headers=headers).status_code, 200)

    def test_blocked_websocket_is_closed_before_handler(self):
        from starlette.websockets import WebSocketDisconnect

        with self.assertRaises(WebSocketDisconnect) as caught:
            with self.client(peer='192.168.1.2').websocket_connect('/unavailable'):
                self.fail('must never upgrade')
        self.assertEqual(caught.exception.code, 1008)
