from pathlib import Path
import subprocess
import sys
import unittest


class FluxSchemaImportTests(unittest.TestCase):
    def test_url_validation_uses_pure_schema_before_main_is_loaded(self):
        script = """
import sys
from unittest.mock import patch
from pydantic import ValidationError

with patch('sqlite3.connect', side_effect=AssertionError('database opened')):
    with patch('pathlib.Path.mkdir', side_effect=AssertionError('directory created')):
        from backend import flux_extensions, flux_workflows, schemas

        components = dict(diffusion_model='unet', clip_l='clip', t5xxl='t5', vae='vae')
        models = (
            (flux_workflows.Input, components),
            (flux_extensions.LoraInput, dict(components, lora_name='style')),
            (flux_extensions.ImageInput, dict(components, image_asset_id='1' * 32)),
        )
        for model, fields in models:
            for raw, normalized in (
                (' http://127.0.0.1:8188/ ', 'http://127.0.0.1:8188'),
                ('https://engine.invalid/proxy///', 'https://engine.invalid/proxy'),
            ):
                assert model(engine_url=raw, **fields).engine_url == normalized
                assert schemas.Settings(comfy_url=raw).comfy_url == normalized
            for raw in (
                'ftp://engine.invalid', 'http://', 'http://user:pass@engine.invalid',
                'https://engine.invalid?token=1', 'https://engine.invalid#preview',
                'http://engine.invalid:bad', 'http://engine.invalid:65536',
            ):
                try:
                    model(engine_url=raw, **fields)
                except ValidationError as error:
                    [issue] = error.errors()
                    assert issue['loc'] == ('engine_url',)
                    assert issue['msg'].startswith('Value error, ')
                else:
                    raise AssertionError(f'invalid URL accepted: {raw}')
        assert 'backend.main' not in sys.modules, 'URL validation loaded the application'

        from backend import main

        assert main.Settings is schemas.Settings
"""
        result = subprocess.run(
            [sys.executable, '-c', script],
            capture_output=True,
            text=True,
            timeout=20,
            cwd=Path(__file__).resolve().parents[1],
        )
        self.assertEqual(result.returncode, 0, result.stderr)
