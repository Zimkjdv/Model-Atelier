"""Published examples bind real PNG bytes, exact recipes and scoped comparisons."""

import hashlib
import io
import json
import unittest
from pathlib import Path

from PIL import Image

from backend import adapter_workflows, flux_workflows, template_context, workflows

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / 'docs/guide'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


class SimpleExampleTests(unittest.TestCase):
    def test_extra_recipes_and_style_tasks_have_exact_real_examples(self):
        index = read(ROOT / 'models/simple-creation-extra-examples-v1.json')['examples']
        registry = read(ROOT / 'models/simple-creation-extra-templates-v1.json')['templates']
        registry += read(ROOT / 'models/simple-style-templates-v1.json')['templates']
        self.assertEqual(len(index), 14)
        self.assertEqual({e['template_id'] for e in index}, {r['id'] for r in registry})
        for model in ('animagine', 'pony', 'flux'):
            self.assertEqual(sum(r['model_id'] == model for r in registry), 4)
        for entry in index:
            name = entry['template_id']
            with self.subTest(template=name):
                record = read(GUIDE / 'examples' / (name + '-v1.json'))
                context = record['template_context']
                expected = template_context.freeze(
                    context['selection'],
                    record['settings'],
                    record['model_metadata'],
                    record['component_metadata'],
                    context['workflow_id'],
                    record['lora_metadata'],
                )
                self.assertEqual(context, expected)
                self.assertFalse(context['modified'])
                self.assertEqual(entry['recipe_sha256'], context['recipe_sha256'])
                self.assertEqual(entry['image_sha256'], record['image']['sha256'])
                self.assertEqual(entry['observations'], record['observations'])
                self.assertEqual(entry['seed'], record['settings']['seed'])
                if name == 'style-reference':
                    expected_graph = adapter_workflows.build(record['settings'], record['job_id'])
                    source = GUIDE / record['source_image']['file']
                    self.assertEqual(
                        hashlib.sha256(source.read_bytes()).hexdigest(),
                        record['source_image']['sha256'],
                    )
                else:
                    builder = flux_workflows.build if name.startswith('flux-') else workflows.build
                    expected_graph = builder(record['settings'])
                self.assertEqual(record['workflow'], expected_graph)
                self.assertTrue(record['local_weights_verified'])
                self.assertEqual(record['source'], 'real_local_comfyui_generation')
                self.image(record)

    def image(self, record):
        location = (GUIDE / record['image']['file']).resolve()
        self.assertTrue(location.is_relative_to(GUIDE.resolve()))
        raw = location.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), record['image']['sha256'])
        self.assertEqual(len(raw), record['image']['bytes'])
        with Image.open(io.BytesIO(raw)) as image:
            self.assertEqual(image.size, (record['image']['width'], record['image']['height']))
        return raw

    def test_three_recipe_examples_match_current_versioned_baseline_and_original_bytes(self):
        index = read(ROOT / 'models/simple-creation-examples-v1.json')
        self.assertEqual(
            {item['template_id'] for item in index['examples']}, {'animagine', 'pony', 'flux'}
        )
        for entry in index['examples']:
            with self.subTest(template=entry['template_id']):
                record = read(GUIDE / 'examples' / (entry['template_id'] + '-v1.json'))
                context = record['template_context']
                expected = template_context.freeze(
                    context['selection'],
                    record['settings'],
                    record['model_metadata'],
                    record['component_metadata'],
                    context['workflow_id'],
                )
                self.assertEqual(context, expected)
                self.assertFalse(context['modified'])
                self.assertEqual(entry['recipe_sha256'], context['recipe_sha256'])
                self.assertEqual(entry['image_sha256'], record['image']['sha256'])
                self.assertEqual(entry['observations'], record['observations'])
                self.assertEqual(record['settings']['seed'], '9007199254740993')
                builder = (
                    flux_workflows.build if entry['template_id'] == 'flux' else workflows.build
                )
                self.assertEqual(record['workflow'], builder(record['settings']))
                self.assertTrue(record['local_weights_verified'])
                self.assertTrue(record['runtime_metadata']['engine']['comfyui'])
                self.assertEqual(record['source'], 'real_local_comfyui_generation')
                self.image(record)

    def test_lora_comparison_changes_only_the_stack_and_preserves_real_loading_evidence(self):
        baseline = read(GUIDE / 'examples/lora-baseline-v1.json')
        styled = read(GUIDE / 'examples/lora-style-v1.json')
        for record in [baseline, styled]:
            self.image(record)
            self.assertEqual(record['date'], '2026-10-23')
            self.assertIn('pixel art', record['settings']['prompt'])
        base_settings = {
            k: v for k, v in baseline['settings'].items() if k not in ('title', 'loras')
        }
        styled_settings = {
            k: v for k, v in styled['settings'].items() if k not in ('title', 'loras')
        }
        self.assertEqual(base_settings, styled_settings)
        self.assertEqual(baseline['settings']['loras'], [])
        self.assertEqual(len(styled['settings']['loras']), 1)
        self.assertEqual(
            styled['settings']['loras'][0]['name'], 'pixel_art_lora_sdxl_comfy_v1.safetensors'
        )
        self.assertEqual(styled['settings']['loras'][0]['strength_model'], 1.0)
        evidence = read(ROOT / styled['evidence'])
        source = next(item for item in evidence['runs'] if item['job_id'] == styled['job_id'])
        self.assertEqual(source['report_sha256'], styled['source_report_sha256'])
        self.assertEqual(source['settings'], styled['settings'])

    def test_reference_comparison_preserves_input_and_varies_only_reference_weight(self):
        baseline = read(GUIDE / 'examples/reference-zero-v1.json')
        styled = read(GUIDE / 'examples/reference-style-v1.json')
        for record in [baseline, styled]:
            self.image(record)
            self.assertEqual(record['workflow_id'], 'checkpoint-ipadapter-reference-v1')
            self.assertEqual(record['settings']['loras'], [])
            self.assertEqual(record['settings']['reference_mode'], 'style')
            source = GUIDE / record['source_image']['file']
            self.assertEqual(
                hashlib.sha256(source.read_bytes()).hexdigest(), record['source_image']['sha256']
            )
        exclude = ('title', 'reference_weight')
        self.assertEqual(
            {k: v for k, v in baseline['settings'].items() if k not in exclude},
            {k: v for k, v in styled['settings'].items() if k not in exclude},
        )
        self.assertEqual(baseline['source_image'], styled['source_image'])
        self.assertEqual(baseline['settings']['reference_weight'], 0.0)
        self.assertEqual(styled['settings']['reference_weight'], 0.6)
