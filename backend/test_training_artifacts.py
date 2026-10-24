from pathlib import Path
import shutil
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import catalog, compute_lease, loras, main, training_artifacts as artifacts
from backend.training_files import digest, file_manifest, read_json
from backend import test_training_runs as fixtures


class ArtifactTests(fixtures.RunFixture):
    def completed(self):
        result = self.prepare()
        folder = Path(result['directory'])
        output = folder / 'output'
        (output / 'model.safetensors').write_bytes(b'synthetic weight fixture')
        state = output / 'model-state'
        state.mkdir()
        compute_lease.atomic_json(state / 'train_state.json', dict(current_step=3))
        (state / 'optimizer.bin').write_bytes(b'synthetic optimizer')
        compute_lease.atomic_json(
            folder / 'checkpoints/step-3.json',
            dict(
                schema_version=1,
                run_id=result['run_id'],
                manifest_sha256=result['manifest_sha256'],
                step=3,
                directory='model-state',
                files=file_manifest(state),
            ),
        )
        compute_lease.atomic_json(
            folder / 'artifacts.json',
            dict(
                schema_version=1,
                run_id=result['run_id'],
                manifest_sha256=result['manifest_sha256'],
                technical_only=True,
                files={
                    'model.safetensors': dict(
                        size_bytes=24, sha256=digest(output / 'model.safetensors')
                    )
                },
            ),
        )
        compute_lease.atomic_json(
            folder / 'state.json',
            dict(status='completed', manifest_sha256=result['manifest_sha256']),
        )
        return result, folder

    def api(self):
        app = main.create_app(data_root=self.root / 'platform')
        app.state.context.initialize()
        client = TestClient(app)
        self.addCleanup(client.close)
        return client, app.state.context

    def test_completed_registration_is_traceable_technical_and_idempotent(self):
        run, folder = self.completed()
        original = digest(folder / 'output/model.safetensors')
        value = artifacts.register(run['run_id'], self.root)
        self.assertTrue(value['technical_only'])
        self.assertEqual(value['quality_status'], 'technical-only')
        self.assertEqual(value['manifest_sha256'], run['manifest_sha256'])
        self.assertEqual(value['dataset']['train_count'], 1)
        self.assertEqual(artifacts.register(run['run_id'], self.root), value)
        self.assertEqual(digest(folder / 'output/model.safetensors'), original)

    def test_nonterminal_failed_active_corrupt_and_unsealed_runs_are_rejected(self):
        run, folder = self.completed()
        with compute_lease.Reservation(self.root, 'training', run['run_id']):
            with self.assertRaises(ValueError):
                artifacts.register(run['run_id'], self.root)
        state = read_json(folder / 'state.json')
        compute_lease.atomic_json(folder / 'state.json', state | dict(status='failed'))
        with self.assertRaises(ValueError):
            artifacts.register(run['run_id'], self.root)
        compute_lease.atomic_json(folder / 'state.json', state)
        (folder / 'output/model.safetensors').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            artifacts.register(run['run_id'], self.root)
        self.assertFalse(artifacts.paths(run['run_id'], self.root)[1].exists())

    def test_installed_hash_and_sidecar_tampering_never_publish(self):
        run, _ = self.completed()
        artifacts.register(run['run_id'], self.root)
        _, weight, sidecar = artifacts.paths(run['run_id'], self.root)
        weight.write_bytes(b'changed')
        with self.assertRaises(ValueError):
            artifacts.verify_installed(run['run_id'], self.root)
        with patch.object(artifacts, 'response', side_effect=AssertionError('no API write')):
            with self.assertRaises(ValueError):
                artifacts.publish(None, run['run_id'], self.root)
        sidecar.write_bytes(b'{}')
        with self.assertRaises(ValueError):
            artifacts.registration(run['run_id'], self.root)

    def test_catalog_publish_uses_existing_api_and_preserves_other_records(self):
        run, _ = self.completed()
        value = artifacts.register(run['run_id'], self.root)
        client, host = self.api()
        engine = 'http://127.0.0.1:8188'
        loras.merge(host.DB, engine, ['old.safetensors', value['filename']])
        loras.update_metadata(host.DB, engine, 'old.safetensors', dict(notes='keep'))
        import httpx
        from unittest.mock import AsyncMock

        remote = AsyncMock()
        remote.__aenter__.return_value = remote
        remote.get.return_value = httpx.Response(
            200,
            json={
                'LoraLoader': {
                    'input': {'required': {'lora_name': [['old.safetensors', value['filename']]]}}
                }
            },
            request=httpx.Request('GET', engine),
        )
        with patch('backend.loras.httpx.AsyncClient', return_value=remote):
            published = artifacts.publish(client, run['run_id'], self.root)
        self.assertIn('TECHNICAL TEST ONLY', published['catalog_entry']['notes'])
        self.assertEqual(published['catalog_entry']['sha256'], value['weight']['sha256'])
        self.assertEqual(loras.read(host.DB, engine)['loras'][-1]['notes'], 'keep')
        self.assertEqual(client.get('/api/jobs').json(), [])

    def test_fixed_evaluation_preserves_both_seeds_empty_baseline_and_no_jobs(self):
        run, _ = self.completed()
        artifacts.register(run['run_id'], self.root)
        (self.root / 'experiments').mkdir()
        shutil.copy(
            artifacts.runs.ROOT / 'experiments/anime-illustration-v1.json',
            self.root / 'experiments',
        )
        client, host = self.api()
        target = self.root / 'evaluation'
        value = artifacts.registration(run['run_id'], self.root)
        engine = 'http://127.0.0.1:8188'
        base_name = Path(value['base']['path']).name
        catalog.merge(host.DB, engine, [base_name])
        catalog.update_metadata(
            host.DB,
            engine,
            base_name,
            {
                key: value['base'][key]
                for key in ('sha256', 'size_bytes', 'version', 'architecture')
            },
        )
        loras.merge(host.DB, engine, [value['filename']])
        loras.update_metadata(host.DB, engine, value['filename'], artifacts.metadata(value))
        result = artifacts.evaluation(client, run['run_id'], target, root=self.root)
        self.assertEqual(result['expected_job_count'], 12)
        self.assertEqual(len(result['plans']), 6)
        self.assertEqual(len(read_json(target / 'review-template.json')['cells']), 6)
        for row in result['plans']:
            variants = row['plan']['variants']
            self.assertEqual([v['settings']['seed'] for v in variants], artifacts.SEEDS)
            expected = (
                []
                if row['branch'] == 'baseline'
                else [
                    dict(
                        name='ma-trained-' + run['run_id'] + '.safetensors',
                        enabled=True,
                        strength_model=1.0,
                        strength_clip=0.0,
                    )
                ]
            )
            self.assertEqual(variants[0]['settings']['loras'], expected)
        saved = artifacts.save_plans(client, target)
        self.assertEqual(artifacts.save_plans(client, target), saved)
        self.assertEqual(len(client.get('/api/experiments/plans').json()), 6)
        self.assertEqual(client.get('/api/jobs').json(), [])
        with self.assertRaises(ValueError):
            artifacts.evaluation(client, run['run_id'], target, root=self.root)
        (target / 'evaluation.json').write_bytes(b'{}')
        with self.assertRaises(ValueError):
            artifacts.save_plans(client, target)

    def test_character_prompts_remain_separate_and_reuse_fixed_r02_source(self):
        document = artifacts.cases('character')
        self.assertEqual(len(document['cases']), 3)
        self.assertEqual(len({v['prompt'] for v in document['cases']}), 3)
        self.assertTrue(all('green eyes' in v['prompt'] for v in document['cases']))

    def test_unsealed_final_state_and_existing_weight_are_never_overwritten(self):
        run, folder = self.completed()
        receipt = folder / 'checkpoints/step-3.json'
        original = receipt.read_bytes()
        receipt.unlink()
        with self.assertRaises(OSError):
            artifacts.register(run['run_id'], self.root)
        receipt.write_bytes(original)
        _, weight, _ = artifacts.paths(run['run_id'], self.root)
        weight.parent.mkdir(parents=True)
        weight.write_bytes(b'keep existing weight')
        with self.assertRaises(ValueError):
            artifacts.register(run['run_id'], self.root)
        self.assertEqual(weight.read_bytes(), b'keep existing weight')

    def test_remote_engine_and_conflicting_identity_do_not_change_metadata(self):
        run, _ = self.completed()
        value = artifacts.register(run['run_id'], self.root)
        client, host = self.api()
        client.put('/api/settings', json=dict(comfy_url='https://remote.invalid'))
        with self.assertRaises(ValueError):
            artifacts.publish(client, run['run_id'], self.root)
        self.assertEqual(loras.read(host.DB, 'https://remote.invalid')['loras'], [])
        engine = 'http://127.0.0.1:8188'
        client.put('/api/settings', json=dict(comfy_url=engine))
        loras.merge(host.DB, engine, [value['filename']])
        loras.update_metadata(host.DB, engine, value['filename'], dict(sha256='c' * 64))
        before = loras.read(host.DB, engine)
        original_response = artifacts.response

        def response(api, method, path, **kwargs):
            return (
                before if path == 'loras/sync' else original_response(api, method, path, **kwargs)
            )

        with patch.object(artifacts, 'response', side_effect=response):
            with self.assertRaises(ValueError):
                artifacts.publish(client, run['run_id'], self.root)
        self.assertEqual(loras.read(host.DB, engine), before)

    def test_technical_acceptance_profiles_preserve_empty_baseline_and_unet_only_choice(self):
        import httpx
        from scripts.verify_trained_lora import runner_type
        from backend.workflows import build

        run, _ = self.completed()
        value = artifacts.register(run['run_id'], self.root)
        settings = []
        with (
            httpx.Client(base_url='http://127.0.0.1:1075') as client,
            patch.object(artifacts, 'registration', return_value=value),
        ):
            for branch in ('baseline', 'candidate'):
                runner = runner_type(run['run_id'], branch)(
                    client, 'http://127.0.0.1:8188', 'animagine-xl-4.0-opt.safetensors'
                )
                settings.append(runner.expected_settings())
        self.assertEqual(len(build(settings[0])), 7)
        self.assertEqual(len(build(settings[1])), 8)
        self.assertEqual(settings[0]['loras'], [])
        self.assertEqual(settings[1]['loras'][0]['strength_clip'], 0.0)
        for key in ('seed', 'prompt', 'width', 'height', 'steps', 'cfg'):
            self.assertEqual(settings[0][key], settings[1][key])
