import tempfile
from pathlib import Path
from unittest import TestCase

from fastapi.testclient import TestClient
from backend import main
from backend.container_main import bridge_gateway
from backend.deployment_profile import Profile


class ContainerDeploymentTests(TestCase):
    def test_native_profiles_cannot_trust_bridge_or_public_addresses(self):
        for kind, peers in [
            ('native', ('172.18.0.1',)),
            ('other', ()),
            ('container', ('0.0.0.0',)),
            ('container', ('8.8.8.8',)),
            ('container', ('224.0.0.1',)),
        ]:
            with self.assertRaises(ValueError):
                Profile(kind, peers)

    def test_container_only_trusts_explicit_gateway_and_loopback_origins(self):
        with tempfile.TemporaryDirectory() as folder:
            app = main.create_app(
                data_root=folder,
                deployment_profile=Profile('container', ('172.18.0.1',)),
                initial_engine_url='http://host.docker.internal:8188',
            )
            app.state.context.initialize()
            with TestClient(
                app, base_url='http://127.0.0.1:8001', client=('172.18.0.1', 1)
            ) as client:
                self.assertEqual(client.get('/api/health').status_code, 200)
                self.assertEqual(
                    client.get('/api/settings').json()['comfy_url'],
                    'http://host.docker.internal:8188',
                )
                self.assertEqual(
                    client.get('/api/health', headers={'Host': 'attacker.invalid'}).status_code, 403
                )
                self.assertEqual(
                    client.get(
                        '/api/health', headers={'Origin': 'https://attacker.invalid'}
                    ).status_code,
                    403,
                )
                report = client.get('/api/deployment').json()
                self.assertEqual(report['mode'], 'container-local')
                self.assertEqual(report['platform']['source'], 'container Python process')
            with TestClient(
                app, base_url='http://127.0.0.1:8001', client=('172.18.0.2', 1)
            ) as stranger:
                self.assertEqual(stranger.get('/api/health').status_code, 403)

    def test_saved_engine_overrides_initial_default_after_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            app = main.create_app(
                data_root=folder, initial_engine_url='http://host.docker.internal:8188'
            )
            app.state.context.initialize()
            with TestClient(
                app, base_url='http://127.0.0.1:8000', client=('127.0.0.1', 1)
            ) as client:
                client.put('/api/settings', json={'comfy_url': 'http://custom-engine.invalid:8188'})
            restarted = main.create_app(
                data_root=folder, initial_engine_url='http://changed-default.invalid:8188'
            )
            with TestClient(
                restarted, base_url='http://127.0.0.1:8000', client=('127.0.0.1', 1)
            ) as client:
                self.assertEqual(
                    client.get('/api/settings').json()['comfy_url'],
                    'http://custom-engine.invalid:8188',
                )

    def test_gateway_is_read_from_kernel_route_not_a_cidr_guess(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'route'
            source.write_text(
                'Iface Destination Gateway Flags\neth0 00000000 010012AC 0003\n', encoding='ascii'
            )
            self.assertEqual(bridge_gateway(source), '172.18.0.1')
            source.write_text('Iface Destination Gateway Flags\n', encoding='ascii')
            with self.assertRaises(ValueError):
                bridge_gateway(source)
