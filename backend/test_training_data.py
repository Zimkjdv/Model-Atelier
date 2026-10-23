import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from backend import training_data as data
from scripts import training_dataset as cli


class DatasetFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'originals'
        self.source.mkdir()
        for name, color in [('a.png', 'red'), ('b.png', 'green'), ('c.png', 'blue')]:
            Image.new('RGB', (48, 64), color).save(self.source / name)
        self.base = cli.expected_base()
        self.dataset = cli.initialize(
            self.source,
            dataset_id='example-style',
            version='v1',
            kind='style',
            subject_id='example-style',
            trigger='ma_example_style',
        )
        self.dataset.images[1].split = 'validation'
        self.dataset.images[2].split = 'test'
        row = self.dataset.images[0]
        row.caption = data.Caption(
            content='1girl, 棕髮, reading a book', status='approved', reviewed_by='fixture reviewer'
        )
        row.provenance = data.Provenance(
            training_use='recorded',
            usage_note='Synthetic test image created by this test.',
            reviewed_by='fixture reviewer',
        )

    def parsed(self, change):
        raw = self.dataset.model_dump(mode='json')
        change(raw)
        return data.Dataset.model_validate(raw)

    def report(self, dataset=None, study=None):
        return data.audit(dataset or self.dataset, self.source, self.base, study)

    def codes(self, dataset=None, study=None):
        return {issue['code'] for issue in self.report(dataset, study)['issues']}

    def study(self):
        rows = []
        for index, row in enumerate(self.dataset.images, 1):
            rows.append(
                dict(
                    index=index,
                    relative_path=row.path,
                    sha256=row.sha256,
                    size=row.size_bytes,
                    width=row.width,
                    height=row.height,
                    duplicate_group=row.group_id,
                    split='holdout' if index == 2 else 'reference',
                    used_as_input=index == 1,
                )
            )
        document = dict(schema_version=1, study_id='example-r02', images=rows)
        return document, data.digest(data.canonical(document))


class DatasetTests(DatasetFixture):
    def test_valid_sources_and_metadata(self):
        self.assertTrue(self.report()['data_ready'])
        self.assertFalse(self.report()['training_started'])

    def test_strict_version_fields_and_types(self):
        for change in [
            lambda x: x.update(schema_version=True),
            lambda x: x.update(schema_version=2),
            lambda x: x.update(extra='x'),
            lambda x: x['images'][0].update(width='48'),
        ]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.parsed(change)

    def test_paths_cannot_escape_or_use_windows_drives(self):
        for name in [
            '../a.png',
            '/a.png',
            'C:/a.png',
            'x\\a.png',
            'x//a.png',
            './a.png',
            'a\n.png',
        ]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.parsed(lambda x: x['images'][0].update(path=name))

    def test_case_insensitive_path_and_id_collisions(self):
        for fields in [dict(path='A.PNG'), dict(id=self.dataset.images[0].id)]:
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                self.parsed(lambda x: x['images'][1].update(**fields))

    def test_groups_never_cross_active_splits(self):
        with self.assertRaises(ValueError):
            self.parsed(lambda x: x['images'][1].update(group_id=x['images'][0]['group_id']))

    def test_equal_bytes_require_same_group(self):
        with self.assertRaises(ValueError):
            self.parsed(lambda x: x['images'][1].update(sha256=x['images'][0]['sha256']))

    def test_multiple_training_variants_are_not_ready(self):
        dataset = self.parsed(
            lambda x: x['images'][1].update(split='train', group_id=x['images'][0]['group_id'])
        )
        self.assertIn('multiple_training_variants', self.codes(dataset))

    def test_caption_review_is_explicit(self):
        for fields in [dict(content=' '), dict(status='pending'), dict(reviewed_by='')]:
            dataset = copy.deepcopy(self.dataset)
            dataset.images[0].caption = data.Caption(
                **(dataset.images[0].caption.model_dump() | fields)
            )
            with self.subTest(fields=fields):
                self.assertIn('caption_review_required', self.codes(dataset))
        with self.assertRaises(ValueError):
            data.Caption(content='first line\nsecond line')

    def test_source_use_record_is_explicit(self):
        for fields in [
            dict(training_use='unreviewed'),
            dict(training_use='exclude'),
            dict(usage_note=''),
            dict(reviewed_by=''),
        ]:
            dataset = copy.deepcopy(self.dataset)
            dataset.images[0].provenance = data.Provenance(
                **(dataset.images[0].provenance.model_dump() | fields)
            )
            with self.subTest(fields=fields):
                self.assertIn('source_use_record_required', self.codes(dataset))

    def test_character_requires_per_image_target_review(self):
        dataset = self.parsed(lambda x: x.update(kind='character', subject_id='brown-green'))
        self.assertIn('target_character_review_required', self.codes(dataset))
        dataset.images[0].identity = 'target'
        dataset.images[0].character_ids = ['brown-green']
        self.assertTrue(self.report(dataset)['data_ready'])
        dataset.images[0].identity = 'mixed'
        self.assertIn('target_character_review_required', self.codes(dataset))

    def test_no_final_test_is_warning_but_seen_test_is_error(self):
        dataset = copy.deepcopy(self.dataset)
        dataset.images[2].split = 'validation'
        report = self.report(dataset)
        self.assertTrue(report['data_ready'])
        self.assertEqual(report['warnings'][0]['code'], 'no_final_test_set')
        self.dataset.images[2].exposure = ['r02_contact_sheet']
        self.assertIn('final_test_previously_exposed', self.codes())

    def test_t01_base_anchor_mismatch(self):
        self.dataset.base_model.sha256 = 'f' * 64
        self.assertIn('base_model_differs_from_t01', self.codes())

    def test_source_integrity_missing_changed_dimensions(self):
        for mutation in ['sha', 'size', 'dimensions', 'missing']:
            dataset = copy.deepcopy(self.dataset)
            row = dataset.images[0]
            if mutation == 'sha':
                row.sha256 = '0' * 64
            if mutation == 'size':
                row.size_bytes += 1
            if mutation == 'dimensions':
                row.width += 1
            if mutation == 'missing':
                row.path = 'missing.png'
            with self.subTest(mutation=mutation):
                self.assertIn('source_integrity', self.codes(dataset))

    def test_invalid_and_animated_image_rejected(self):
        (self.source / 'bad.png').write_bytes(b'not an image')
        with self.assertRaises(ValueError):
            data.read_source(self.source, 'bad.png')
        frames = [Image.new('RGB', (4, 4), c) for c in ('red', 'blue')]
        frames[0].save(self.source / 'motion.png', save_all=True, append_images=frames[1:])
        with self.assertRaises(ValueError):
            data.read_source(self.source, 'motion.png')

    def test_source_links_rejected(self):
        original = Path.is_symlink
        with patch.object(Path, 'is_symlink', lambda p: p.name == 'a.png' or original(p)):
            with self.assertRaises(ValueError):
                data.read_source(self.source, 'a.png')
            with self.assertRaises(ValueError):
                cli.inventory(self.source)

    def test_duplicate_json_keys_rejected(self):
        path = self.root / 'duplicate.json'
        path.write_text('{"schema_version":1,"schema_version":2}', encoding='utf-8')
        with self.assertRaises(ValueError):
            data.load(path)

    def test_oversize_manifest_rejected(self):
        path = self.root / 'large.json'
        path.write_bytes(b' ' * (data.MAX_MANIFEST_BYTES + 1))
        with self.assertRaises(ValueError):
            data.load(path)

    def test_init_exact_alias_is_excluded_and_not_approved(self):
        (self.source / 'd.png').write_bytes((self.source / 'a.png').read_bytes())
        dataset = cli.initialize(
            self.source,
            dataset_id='example',
            version='v2',
            kind='character',
            subject_id='target',
            trigger='ma_target',
        )
        self.assertEqual(dataset.images[-1].split, 'excluded')
        self.assertEqual(dataset.images[-1].group_id, dataset.images[0].group_id)
        self.assertEqual(dataset.images[0].identity, 'unreviewed')
        self.assertEqual(dataset.images[0].caption.status, 'pending')

    def test_study_bridge_preserves_holdout_and_exposure(self):
        study = self.study()
        dataset = cli.initialize(
            self.source,
            dataset_id='example',
            version='v2',
            kind='style',
            subject_id='style',
            trigger='ma_style',
            study=study,
        )
        self.assertEqual(dataset.images[1].split, 'validation')
        self.assertEqual(dataset.images[0].exposure, ['r02_contact_sheet', 'inference_reference'])
        self.assertIn('parent_study_required', self.codes(dataset))
        self.assertNotIn('parent_study_record_changed', self.codes(dataset, study))
        dataset.images[1].split = 'train'
        dataset.images[0].exposure = []
        self.assertIn('parent_study_record_changed', self.codes(dataset, study))
        self.assertIn('parent_study_mismatch', self.codes(dataset, (study[0], '0' * 64)))

    def test_study_bridge_refuses_changed_inventory_or_source(self):
        study = self.study()
        for change in ['inventory', 'sha']:
            modified = copy.deepcopy(study[0])
            if change == 'inventory':
                modified['images'].pop()
            else:
                modified['images'][0]['sha256'] = '0' * 64
            with self.subTest(change=change), self.assertRaises(ValueError):
                cli.initialize(
                    self.source,
                    dataset_id='example',
                    version='v2',
                    kind='style',
                    subject_id='style',
                    trigger='ma_style',
                    study=(modified, study[1]),
                )

    def test_cli_readiness_exit_and_exclusive_report(self):
        manifest = self.root / 'dataset.json'
        manifest.write_bytes(data.canonical(self.dataset))
        args = [
            'check',
            str(manifest),
            '--source-root',
            str(self.source),
            '--report',
            str(self.root / 'report.json'),
        ]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(args), 0)
            self.assertEqual(cli.main(args), 1)
            self.dataset.images[0].caption.status = 'pending'
            manifest.write_bytes(data.canonical(self.dataset))
            self.assertEqual(cli.main(args[:-2]), 2)


if __name__ == '__main__':
    unittest.main()
