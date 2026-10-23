import copy
import io
import json
from pathlib import Path
import tomllib
from unittest.mock import patch

from PIL import Image

from backend import training_data as data, training_bundle as bundle
from backend.test_training_data import DatasetFixture


class BundleTests(DatasetFixture):
    def export(self, dataset=None, name='bundle-v1'):
        target = self.root / name
        report = bundle.export(dataset or self.dataset, self.source, target, self.base)
        return target, report

    def test_export_only_train_and_verify_caption_toml(self):
        target, report = self.export()
        self.assertTrue(report['bundle_verified'])
        self.assertEqual(report['train_count'], 1)
        names = {p.name for p in (target / 'train').iterdir()}
        row = self.dataset.images[0]
        self.assertEqual(names, {row.id + '.png', row.id + '.txt'})
        self.assertEqual(
            (target / 'train' / (row.id + '.txt')).read_text(encoding='utf-8'),
            'ma_example_style, 1girl, 棕髮, reading a book\n',
        )
        config = tomllib.loads((target / 'dataset.toml').read_text(encoding='utf-8'))
        self.assertEqual(config['datasets'][0]['validation_split'], 0.0)
        self.assertEqual(
            config['datasets'][0]['subsets'][0]['image_dir'],
            (target / 'train').resolve().as_posix(),
        )
        self.assertEqual(
            data.read_json(target / 'bundle.json')[0]['trainer_revision'], bundle.TRAINER
        )
        self.assertEqual(
            (self.source / 'a.png').read_bytes(), data.read_source(self.source, 'a.png')[1]
        )

    def test_unreviewed_data_never_creates_output(self):
        self.dataset.images[0].caption.status = 'pending'
        with self.assertRaises(ValueError):
            self.export()
        self.assertFalse((self.root / 'bundle-v1').exists())

    def test_oversize_metadata_never_creates_output(self):
        with patch.object(data, 'MAX_MANIFEST_BYTES', 100), self.assertRaises(ValueError):
            self.export()
        self.assertFalse((self.root / 'bundle-v1').exists())

    def test_no_overwrite_existing_bundle_or_source_location(self):
        target, _ = self.export()
        before = (target / 'bundle.json').read_bytes()
        with self.assertRaises(ValueError):
            self.export()
        self.assertEqual((target / 'bundle.json').read_bytes(), before)
        for destination in [self.source / 'new-bundle', self.root]:
            with self.subTest(destination=destination), self.assertRaises(ValueError):
                bundle.export(self.dataset, self.source, destination, self.base)

    def test_interrupted_write_leaves_unsealed_directory(self):
        original = bundle.write_new

        def fail(path, raw):
            if path.suffix == '.png':
                raise OSError('simulated disk failure')
            return original(path, raw)

        with patch.object(bundle, 'write_new', fail), self.assertRaises(OSError):
            self.export()
        target = self.root / 'bundle-v1'
        self.assertTrue(target.is_dir())
        self.assertFalse((target / 'bundle.json').exists())
        with self.assertRaises(OSError):
            bundle.verify(target, self.base)
        with self.assertRaises(ValueError):
            self.export()

    def test_source_changed_during_export_does_not_seal(self):
        original = bundle.write_new

        def change(path, raw):
            original(path, raw)
            if path.name == 'dataset.toml':
                (self.source / 'a.png').write_bytes(b'changed')

        with patch.object(bundle, 'write_new', change), self.assertRaises(ValueError):
            self.export()
        self.assertFalse((self.root / 'bundle-v1' / 'bundle.json').exists())

    def test_tamper_each_artifact_detected(self):
        for index, name in enumerate(
            ['dataset.json', 'dataset.toml', 'train/img-0001.png', 'train/img-0001.txt']
        ):
            target, _ = self.export(name=f'bundle-{index}')
            (target / name).write_bytes(b'changed')
            with self.subTest(name=name), self.assertRaises(ValueError):
                bundle.verify(target, self.base)

    def test_injected_training_image_and_receipt_traversal_rejected(self):
        target, _ = self.export()
        (target / 'train' / 'holdout.png').write_bytes((self.source / 'b.png').read_bytes())
        with self.assertRaises(ValueError):
            bundle.verify(target, self.base)
        target, _ = self.export(name='bundle-v2')
        receipt = data.read_json(target / 'bundle.json')[0]
        receipt['files']['../outside.png'] = dict(sha256='0' * 64, size_bytes=1)
        (target / 'bundle.json').write_bytes(data.canonical(receipt))
        with self.assertRaises(ValueError):
            bundle.verify(target, self.base)

    def test_resealed_caption_and_config_still_must_match_contract(self):
        for index, name in enumerate(['train/img-0001.txt', 'dataset.toml']):
            target, _ = self.export(name=f'bundle-{index}')
            raw = (
                b'wrong caption'
                if name.endswith('.txt')
                else b'[general]\ncaption_extension=".caption"\n'
            )
            (target / name).write_bytes(raw)
            receipt = data.read_json(target / 'bundle.json')[0]
            receipt['files'][name] = dict(sha256=data.digest(raw), size_bytes=len(raw))
            (target / 'bundle.json').write_bytes(data.canonical(receipt))
            with self.subTest(name=name), self.assertRaises(ValueError):
                bundle.verify(target, self.base)

    def test_changed_manifest_metadata_rejected_after_reseal(self):
        target, _ = self.export()
        modified = copy.deepcopy(self.dataset)
        modified.images[0].caption.status = 'pending'
        raw = data.canonical(modified)
        (target / 'dataset.json').write_bytes(raw)
        receipt = data.read_json(target / 'bundle.json')[0]
        receipt['manifest_sha256'] = data.digest(raw)
        receipt['files']['dataset.json'] = dict(sha256=data.digest(raw), size_bytes=len(raw))
        (target / 'bundle.json').write_bytes(data.canonical(receipt))
        with self.assertRaises(ValueError):
            bundle.verify(target, self.base)

    def test_normalize_alpha_exif_no_upscale_and_bound(self):
        stream = io.BytesIO()
        Image.new('RGBA', (10, 20), (0, 0, 0, 0)).save(stream, 'PNG')
        raw, size = data.normalized(stream.getvalue())
        with Image.open(io.BytesIO(raw)) as im:
            self.assertEqual(im.getpixel((0, 0)), (255, 255, 255))
            self.assertEqual(size, (10, 20))
        stream = io.BytesIO()
        image = Image.new('RGB', (3000, 1000), 'red')
        exif = image.getexif()
        exif[274] = 6
        image.save(stream, 'JPEG', exif=exif)
        raw, size = data.normalized(stream.getvalue())
        self.assertEqual(size, (683, 2048))
        with Image.open(io.BytesIO(raw)) as im:
            self.assertFalse(im.getexif())

    def test_schema_file_matches_generated_contract(self):
        path = Path(__file__).resolve().parents[1] / 'schemas/training-dataset-v1.schema.json'
        self.assertEqual(
            json.loads(path.read_text(encoding='utf-8')), data.Dataset.model_json_schema()
        )
