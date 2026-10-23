"""CPU-only immutable training data exports. No trainer or model imports."""

import json
import io
from pathlib import Path
import tomllib

from PIL import Image, __version__ as pillow_version

from backend import training_data as data

TRAINER = '11d8cedd0c67b93a10f8b2d75f43554f6f12c794'
PREPROCESSING = 'exif-white-rgb-png-max2048-v1'


def safe_output(path, source_root=None):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise ValueError('輸出路徑不可經過連結')
    path = path.resolve()
    if source_root is not None:
        source = Path(source_root).resolve(strict=True)
        if path.is_relative_to(source) or source.is_relative_to(path):
            raise ValueError('輸出不得位於原圖目錄或其上層')
    if path.exists():
        raise ValueError('輸出已存在；請指定新的版本／位置')
    return path


def write_new(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as file:
        file.write(raw)


def caption(dataset, row):
    return f'{dataset.trigger}, {row.caption.content.strip()}\n'.encode('utf-8')


def configuration(root):
    image_dir = json.dumps((Path(root).resolve() / 'train').as_posix(), ensure_ascii=False)
    return (
        f'[general]\ncaption_extension = ".txt"\nshuffle_caption = false\nkeep_tokens = 0\n\n'
        f'[[datasets]]\nresolution = [1024, 1024]\nbatch_size = 1\nenable_bucket = true\n'
        f'bucket_no_upscale = true\nbucket_reso_steps = 64\nvalidation_split = 0.0\n\n'
        f'[[datasets.subsets]]\nimage_dir = {image_dir}\nnum_repeats = 1\n'
    ).encode('utf-8')


def export(dataset, source_root, output, expected_base, study=None):
    manifest_raw = data.manifest_bytes(dataset)
    report = data.audit(dataset, source_root, expected_base, study)
    if not report['data_ready']:
        raise ValueError('資料尚未通過檢查；先執行 check 查看問題')
    target = safe_output(output, source_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.mkdir()  # Exclusive publication location; failure leaves an unsealed directory.
    files, records = {}, []

    def save(name, raw):
        write_new(target / name, raw)
        files[name] = dict(sha256=data.digest(raw), size_bytes=len(raw))

    save('dataset.json', manifest_raw)
    save('dataset.toml', configuration(target))
    for row in dataset.images:
        if row.split != 'train':
            continue
        _, raw = data.read_source(source_root, row.path, row)
        png, size = data.normalized(raw)
        save(f'train/{row.id}.png', png)
        save(f'train/{row.id}.txt', caption(dataset, row))
        records.append(
            dict(image_id=row.id, source_sha256=row.sha256, width=size[0], height=size[1])
        )
    if not data.audit(dataset, source_root, expected_base, study)['data_ready']:
        raise ValueError('寫入期間來源已變動；資料包未封存')
    receipt = dict(
        schema_version=1,
        manifest_sha256=data.digest(data.canonical(dataset)),
        trainer_revision=TRAINER,
        preprocessing=PREPROCESSING,
        pillow_version=pillow_version,
        records=records,
        files=files,
        training_started=False,
    )
    save_receipt = data.canonical(receipt)
    write_new(
        target / 'bundle.json', save_receipt
    )  # Seal last; never overwrite or remove partial data.
    return verify(target, expected_base, study)


def verify(root, expected_base, study=None):
    root = Path(root).resolve(strict=True)
    receipt = data.read_json(data.source_path(root, 'bundle.json'))[0]
    keys = {
        'schema_version',
        'manifest_sha256',
        'trainer_revision',
        'preprocessing',
        'pillow_version',
        'records',
        'files',
        'training_started',
    }
    if (
        set(receipt) != keys
        or type(receipt['schema_version']) is not int
        or receipt['schema_version'] != 1
        or receipt['trainer_revision'] != TRAINER
        or receipt['preprocessing'] != PREPROCESSING
        or receipt['training_started'] is not False
    ):
        raise ValueError('資料包封存格式／介面版本無效')
    files = receipt['files']
    if not isinstance(files, dict) or len(files) > 20002:
        raise ValueError('資料包檔案清單無效')
    actual = set()
    for path in root.rglob('*'):
        if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
            raise ValueError('資料包不接受連結')
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    if actual != set(files) | {'bundle.json'}:
        raise ValueError('資料包有遺漏或額外檔案')
    for name, identity in files.items():
        path = data.source_path(root, name)
        if (
            set(identity) != {'sha256', 'size_bytes'}
            or type(identity['size_bytes']) is not int
            or not 0 < identity['size_bytes'] <= data.MAX_BYTES
        ):
            raise ValueError('資料包檔案身分無效')
        with path.open('rb') as file:
            raw = file.read(identity['size_bytes'] + 1)
        if len(raw) != identity['size_bytes'] or data.digest(raw) != identity['sha256']:
            raise ValueError('資料包內容 hash／大小不同')
    dataset = data.load(root / 'dataset.json')
    if (
        data.digest(data.canonical(dataset)) != receipt['manifest_sha256']
        or dataset.base_model != expected_base
    ):
        raise ValueError('資料清單／基底身分不同')
    # Metadata checks still run, but source integrity here refers to exported bytes below.
    # The source images are deliberately absent from portable bundles.
    report = data.audit_metadata(dataset, expected_base, study)
    if not report['data_ready']:
        raise ValueError('資料包 metadata 不符合出口條件')
    expected_files = {'dataset.json', 'dataset.toml'}
    records = []
    for row in dataset.images:
        if row.split != 'train':
            continue
        png_name, txt_name = f'train/{row.id}.png', f'train/{row.id}.txt'
        expected_files.update((png_name, txt_name))
        identity, raw = data.read_source(root, png_name)
        with Image.open(io.BytesIO(raw)) as image:
            if image.format != 'PNG' or image.mode != 'RGB' or max(image.size) > 2048:
                raise ValueError('出口圖片不符合正規化契約')
        if (root / txt_name).read_bytes() != caption(dataset, row):
            raise ValueError('caption 與資料清單不同')
        records.append(
            dict(
                image_id=row.id,
                source_sha256=row.sha256,
                width=identity['width'],
                height=identity['height'],
            )
        )
    if set(files) != expected_files or receipt['records'] != records:
        raise ValueError('資料包訓練圖片與清單不同')
    config_raw = (root / 'dataset.toml').read_bytes()
    tomllib.loads(config_raw.decode('utf-8'))
    if config_raw != configuration(root):
        raise ValueError('dataset TOML 已變更或資料包已移動；請重新匯出')
    return dict(
        bundle_verified=True,
        manifest_sha256=receipt['manifest_sha256'],
        train_count=len(records),
        training_started=False,
    )
