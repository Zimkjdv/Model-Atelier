import asyncio
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

import httpx
from fastapi.testclient import TestClient

from backend.main import create_app


class PromptConverterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.calls = []
        self.mode = 'ok'
        self.content = json.dumps({'prompt': 'A black cat by a window, without a collar.'})
        self.app = create_app(data_root=self.root, prompt_client_factory=self.factory)
        self.app.state.context.initialize()
        self.client = TestClient(self.app, base_url='http://127.0.0.1', client=('127.0.0.1', 123))

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def factory(self, **kwargs):
        self.assertFalse(kwargs['trust_env'])
        self.assertFalse(kwargs['follow_redirects'])
        return httpx.AsyncClient(transport=httpx.MockTransport(self.engine), **kwargs)

    def engine(self, request):
        self.calls.append(request)
        if self.mode == 'offline':
            raise httpx.ConnectError('PRIVATE', request=request)
        if self.mode == 'timeout':
            raise httpx.ReadTimeout('PRIVATE', request=request)
        if self.mode == 'missing':
            return httpx.Response(404, json={'error': 'PRIVATE'})
        if self.mode == 'redirect':
            return httpx.Response(307, headers={'location': 'https://example.com'})
        if self.mode == 'invalid-json':
            return httpx.Response(200, content=b'not json')
        if self.mode == 'oversized':
            return httpx.Response(200, content=b' ' * (256 * 1024 + 1))
        if request.url.path == '/api/show':
            return httpx.Response(
                200,
                json={
                    'details': {
                        'family': 'qwen35',
                        'parameter_size': '2B',
                        'quantization_level': 'Q4_K_M',
                    },
                    **({'remote_host': 'https://ollama.com'} if self.mode == 'cloud' else {}),
                },
            )
        return httpx.Response(
            200,
            json={
                'done': True,
                'done_reason': 'length' if self.mode == 'truncated' else 'stop',
                'message': {'content': self.content},
            },
        )

    def convert(self, **values):
        return self.client.post(
            '/api/prompt-converter/convert',
            json={
                'description': '一隻黑貓坐在窗邊，不要項圈',
                **values,
            },
        )

    def test_local_settings_persist_without_changing_engine_settings(self):
        original = self.client.get('/api/settings').json()
        saved = self.client.put(
            '/api/prompt-converter/settings',
            json={
                'base_url': 'http://localhost:11435/',
                'model': 'qwen3.5:2b',
            },
        )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()['base_url'], 'http://127.0.0.1:11435')
        other = create_app(data_root=self.root)
        with TestClient(other, base_url='http://127.0.0.1', client=('127.0.0.1', 123)) as client:
            self.assertEqual(client.get('/api/prompt-converter/settings').json(), saved.json())
        self.assertEqual(self.client.get('/api/settings').json(), original)
        self.assertEqual(self.calls, [])

    def test_reject_remote_credentials_paths_redirect_and_cloud_settings(self):
        for value in [
            'https://localhost:11434',
            'http://192.168.1.1',
            'http://localhost.evil',
            'http://user@localhost',
            'http://localhost/api',
            'http://localhost:0',
            'http://localhost:99999',
            'http://localhost?remote=1',
        ]:
            with self.subTest(value=value):
                response = self.client.put(
                    '/api/prompt-converter/settings', json={'base_url': value}
                )
                self.assertEqual(response.status_code, 422)
        self.assertEqual(
            self.client.put(
                '/api/prompt-converter/settings', json={'model': 'qwen:cloud'}
            ).status_code,
            422,
        )
        self.assertEqual(self.calls, [])

    def test_conversion_does_not_reserve_or_submit_image_or_persist_description(self):
        response = self.convert()
        self.assertEqual(response.status_code, 200, response.text)
        value = response.json()
        self.assertIn('without a collar', value['prompt'])
        self.assertEqual(value['execution'], 'cpu-requested')
        self.assertEqual([r.url.path for r in self.calls], ['/api/show', '/api/chat'])
        body = json.loads(self.calls[1].content)
        self.assertFalse(body['think'])
        self.assertFalse(body['stream'])
        self.assertEqual(body['keep_alive'], 0)
        self.assertEqual(body['options']['num_gpu'], 0)
        self.assertEqual(body['options']['num_ctx'], 8192)
        with closing(sqlite3.connect(self.app.state.context.DB)) as db:
            rows = db.execute('SELECT key, value FROM settings').fetchall()
        self.assertFalse(any('黑貓' in value or key.startswith('job:') for key, value in rows))

    def test_missing_trigger_is_restored_verbatim_and_pony_prefix_is_explicit(self):
        value = self.convert(
            profile='pony', style='tags', protected_terms=['My_LoRA', '角色甲']
        ).json()
        self.assertTrue(
            value['prompt'].startswith('score_9, score_8_up, score_7_up, My_LoRA, 角色甲')
        )
        body = json.loads(self.calls[-1].content)
        source = json.loads(body['messages'][1]['content'])
        self.assertEqual(source['style'], 'tags')
        self.assertEqual(source['protected_terms'], ['My_LoRA', '角色甲'])

    def test_existing_trigger_is_not_duplicated_and_general_has_no_pony_tags(self):
        self.content = json.dumps({'prompt': 'TokenX, a cat'})
        value = self.convert(protected_terms=['TokenX']).json()['prompt']
        self.assertEqual(value, 'TokenX, a cat')

    def test_offline_timeout_missing_cloud_redirect_and_malformed_fail_without_retry(self):
        for mode, expected in [
            ('offline', 503),
            ('timeout', 504),
            ('missing', 404),
            ('cloud', 422),
            ('redirect', 502),
            ('invalid-json', 502),
            ('oversized', 502),
        ]:
            with self.subTest(mode=mode):
                self.calls.clear()
                self.mode = mode
                response = self.convert()
                self.assertEqual(response.status_code, expected, response.text)
                self.assertEqual(len(self.calls), 1)
                self.assertNotIn('PRIVATE', response.text)

    def test_reject_truncation_chinese_empty_thinking_and_invalid_structure(self):
        for content in [
            'not json',
            '{}',
            '{"prompt":1}',
            '{"prompt":""}',
            '{"prompt":"一隻貓"}',
            '{"prompt":"<think>cat"}',
            '{"prompt":"cat","extra":"unexpected"}',
        ]:
            with self.subTest(content=content):
                self.content = content
                self.assertEqual(self.convert().status_code, 502)
        self.mode = 'truncated'
        self.content = '{"prompt":"A cat"}'
        self.assertEqual(self.convert().status_code, 502)

    def test_empty_long_and_unknown_requests_do_not_call_llm(self):
        for values in [
            {'description': ' '},
            {'description': 'a' * 2001},
            {'profile': 'unknown'},
            {'style': 'unknown'},
            {'protected_terms': ['']},
            {'seed': 1},
            {'description': '山' * 1900, 'protected_terms': ['字' * 150] * 3},
        ]:
            with self.subTest(values=values):
                self.assertEqual(self.convert(**values).status_code, 422)
        self.assertEqual(self.calls, [])

    def test_status_checks_model_without_loading_chat(self):
        response = self.client.get('/api/prompt-converter/status')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['available'])
        self.assertEqual([r.url.path for r in self.calls], ['/api/show'])

    def test_two_apps_have_independent_settings(self):
        self.client.put('/api/prompt-converter/settings', json={'model': 'local-other:2b'})
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(data_root=directory)
            with TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 1)) as client:
                self.assertEqual(
                    client.get('/api/prompt-converter/settings').json()['model'], 'qwen3.5:2b'
                )

    def test_concurrent_requests_are_rejected_before_second_model_call(self):
        async def run():
            entered, release = asyncio.Event(), asyncio.Event()

            async def handler(request):
                if request.url.path == '/api/chat':
                    entered.set()
                    await release.wait()
                return self.engine(request)

            app = create_app(
                data_root=self.root,
                prompt_client_factory=lambda **kw: httpx.AsyncClient(
                    transport=httpx.MockTransport(handler), **kw
                ),
            )
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app, client=('127.0.0.1', 1)),
                base_url='http://127.0.0.1',
            ) as client:
                first = asyncio.create_task(
                    client.post('/api/prompt-converter/convert', json={'description': '貓'})
                )
                await asyncio.wait_for(entered.wait(), 5)
                second = await client.post(
                    '/api/prompt-converter/convert', json={'description': '狗'}
                )
                self.assertEqual(second.status_code, 409)
                release.set()
                self.assertEqual((await first).status_code, 200)

        asyncio.run(run())
