import unittest
from backend import model_profiles, workflows


class WorkflowDescriptionTests(unittest.TestCase):
    def test_supported_and_unknown_models_describe_only_implemented_fields(self):
        for kind in ('sd1', 'sdxl', 'unknown'):
            value = model_profiles.profile('http://127.0.0.1:8188', dict(name='sample', architecture=kind))['workflow']
            self.assertEqual(set(value['fields']), {'prompt', 'negative_prompt', 'seed', 'width', 'height',
                                                   'steps', 'cfg', 'sampler_name', 'scheduler', 'denoise', 'loras'})
            self.assertFalse(value['reference_images'])
            self.assertTrue(value['lora'])
            self.assertEqual(value['max_loras'], 1)
            self.assertEqual(value['batch_size'], 1)
            if kind == 'unknown':
                self.assertEqual(value['verification'], 'engine_validation_required')

    def test_known_unsupported_architectures_have_no_editable_workflow(self):
        for kind in ('flux', 'sd3', 'other'):
            value = model_profiles.profile('http://127.0.0.1:8188', dict(name='sample', architecture=kind))
            self.assertIsNone(value['workflow'])
            self.assertFalse(value['compatibility']['allows_submission'])

    def test_descriptors_do_not_share_mutable_field_lists(self):
        first = model_profiles.workflow_description('sdxl')
        first['fields'].clear()
        self.assertEqual(len(model_profiles.workflow_description('sdxl')['fields']), 11)
