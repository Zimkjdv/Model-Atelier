"""Versioned local dataset contracts and read-only source checks; no training runtime."""

from collections import Counter, defaultdict
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
from typing import Literal

from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_BYTES = 64 * 1024 * 1024
MAX_PIXELS = 40_000_000
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


def relative_path(value):
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 1024
        or '\\' in value
        or ':' in value
        or any(ord(c) < 32 for c in value)
    ):
        raise ValueError('需使用不含磁碟／反斜線／控制字元的相對路徑')
    parts = value.split('/')
    if any(p in ('', '.', '..') for p in parts) or PurePosixPath(value).is_absolute():
        raise ValueError('不允許絕對路徑、空路徑或上層目錄')
    return value


class BaseAnchor(Contract):
    id: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=100)
    architecture: Literal['sdxl']
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    size_bytes: int = Field(gt=0, le=9007199254740991)
    source_revision: str = Field(pattern=r'^[0-9a-f]{40}$')


class Caption(Contract):
    content: str = Field(default='', max_length=4000)
    style_description: str = Field(default='', max_length=2000)
    status: Literal['pending', 'approved', 'rejected'] = 'pending'
    reviewed_by: str = Field(default='', max_length=200)

    @field_validator('content')
    @classmethod
    def single_line(cls, value):
        if any(ord(c) < 32 for c in value):
            raise ValueError('caption 需為單行文字，避免 trainer 只讀第一行')
        return value


class Provenance(Contract):
    attribution: str = Field(default='', max_length=500)
    work_id: str = Field(default='', max_length=200)
    source_url: str = Field(default='', max_length=2048)
    training_use: Literal['unreviewed', 'recorded', 'exclude'] = 'unreviewed'
    usage_note: str = Field(default='', max_length=4000)
    reviewed_by: str = Field(default='', max_length=200)

    @field_validator('source_url')
    @classmethod
    def source_link(cls, value):
        from backend.schemas import Settings

        return Settings.validate_url(value) if value else ''


class ImageRecord(Contract):
    id: str = Field(pattern=r'^[a-z0-9][a-z0-9_-]{0,79}$')
    path: str
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    size_bytes: int = Field(gt=0, le=MAX_BYTES)
    width: int = Field(gt=0, le=65535)
    height: int = Field(gt=0, le=65535)
    group_id: str = Field(pattern=r'^[a-z0-9][a-z0-9_-]{0,79}$')
    split: Literal['train', 'validation', 'test', 'excluded']
    exclusion_reason: str = Field(default='', max_length=2000)
    exposure: list[
        Literal[
            'r02_contact_sheet', 'inference_reference', 'tuning', 'training', 'final_evaluation'
        ]
    ] = Field(default_factory=list, max_length=5)
    identity: Literal['unreviewed', 'target', 'other', 'mixed'] = 'unreviewed'
    character_ids: list[str] = Field(default_factory=list, max_length=16)
    caption: Caption = Field(default_factory=Caption)
    provenance: Provenance = Field(default_factory=Provenance)

    _path = field_validator('path')(relative_path)

    @model_validator(mode='after')
    def bounded(self):
        if self.width * self.height > MAX_PIXELS:
            raise ValueError('原圖不可超過 4000 萬像素')
        if len(set(self.exposure)) != len(self.exposure) or len(set(self.character_ids)) != len(
            self.character_ids
        ):
            raise ValueError('曝光／角色不得重複')
        if any(not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,79}', c) for c in self.character_ids):
            raise ValueError('角色 ID 無效')
        if self.split == 'excluded' and not self.exclusion_reason.strip():
            raise ValueError('排除圖片需記錄原因')
        return self


class StudyAnchor(Contract):
    id: str = Field(min_length=1, max_length=100)
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')


class Dataset(Contract):
    schema_version: Literal[1] = 1
    dataset_id: str = Field(pattern=r'^[a-z0-9][a-z0-9_-]{0,79}$')
    version: str = Field(pattern=r'^[a-z0-9][a-z0-9_.-]{0,79}$')
    kind: Literal['style', 'character']
    subject_id: str = Field(pattern=r'^[a-z0-9][a-z0-9_-]{0,79}$')
    trigger: str = Field(pattern=r'^[a-z][a-z0-9_]{2,63}$')
    requirements_version: Literal['anime-training-requirements-v1'] = (
        'anime-training-requirements-v1'
    )
    base_model: BaseAnchor
    parent_study: StudyAnchor | None = None
    images: list[ImageRecord] = Field(min_length=1, max_length=10000)

    @field_validator('schema_version', mode='before')
    @classmethod
    def integer_version(cls, value):
        if type(value) is not int:
            raise ValueError('schema_version 必須是整數')
        return value

    @model_validator(mode='after')
    def consistency(self):
        if len({r.id for r in self.images}) != len(self.images) or len(
            {r.path.casefold() for r in self.images}
        ) != len(self.images):
            raise ValueError('圖片 ID／路徑（含大小寫差異）重複')
        groups, hashes = defaultdict(set), defaultdict(set)
        for row in self.images:
            hashes[row.sha256].add(row.group_id)
            if row.split != 'excluded':
                groups[row.group_id].add(row.split)
        if any(len(s) > 1 for s in hashes.values()):
            raise ValueError('完全相同內容必須在同一原作群組')
        if any(len(s) > 1 for s in groups.values()):
            raise ValueError('同原作／差分群組不可跨 train、validation、test')
        return self


def canonical(value):
    if isinstance(value, BaseModel):
        value = value.model_dump(mode='json')
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False
    ).encode('utf-8')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def manifest_bytes(dataset):
    raw = canonical(dataset)
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError('資料清單超過 8 MiB；請縮小資料集或標註')
    return raw


def read_json(path):
    with Path(path).open('rb') as file:
        raw = file.read(MAX_MANIFEST_BYTES + 1)
    return parse_json(raw)


def parse_json(raw):
    """Use the same bounded UTF-8/duplicate-key rules for files and web imports."""
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError('資料清單超過 8 MiB')

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('JSON 欄位重複：' + key)
            result[key] = value
        return result

    return json.loads(raw.decode('utf-8'), object_pairs_hook=unique), digest(raw)


def load(path):
    return Dataset.model_validate(read_json(path)[0])


def source_path(root, name):
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('來源必須是目錄')
    relative_path(name)
    path = root
    for part in name.split('/'):
        path = path / part
        if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
            raise ValueError('來源不接受 symlink')
    if not path.resolve(strict=True).is_relative_to(root) or not path.is_file():
        raise ValueError('圖片必須位於指定來源目錄')
    return path


def read_source(root, name, expected=None):
    path = source_path(root, name)
    with path.open('rb') as file:
        raw = file.read(MAX_BYTES + 1)
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError('原圖需為 1 byte 至 64 MiB')
    identity = dict(sha256=digest(raw), size_bytes=len(raw))
    if expected and (
        identity['sha256'] != expected.sha256 or identity['size_bytes'] != expected.size_bytes
    ):
        raise ValueError('原圖 SHA256／大小已變更')
    try:
        with Image.open(io.BytesIO(raw)) as im:
            if (
                im.format not in ('PNG', 'JPEG', 'WEBP')
                or getattr(im, 'n_frames', 1) != 1
                or im.width * im.height > MAX_PIXELS
            ):
                raise ValueError('只支援單張 PNG／JPEG／WebP，且不可超過 4000 萬像素')
            identity.update(width=im.width, height=im.height)
            if expected and (im.width, im.height) != (expected.width, expected.height):
                raise ValueError('原圖尺寸與清單不同')
            im.load()
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ValueError('圖片無法完整解碼') from exc
    return identity, raw


def audit_metadata(dataset, expected_base, study=None):
    issues, warnings = [], []

    def issue(code, row=None):
        issues.append(dict(code=code, image_id=row.id if row else None))

    if dataset.base_model != expected_base:
        issue('base_model_differs_from_t01')
    if dataset.parent_study:
        if study is None:
            issue('parent_study_required')
        else:
            document, sha = study
            if (
                document.get('schema_version') != 1
                or sha != dataset.parent_study.sha256
                or document.get('study_id') != dataset.parent_study.id
            ):
                issue('parent_study_mismatch')
            else:
                originals = {r['relative_path']: r for r in document['images']}
                if set(originals) != {r.path for r in dataset.images}:
                    issue('parent_study_inventory_changed')
                for row in dataset.images:
                    original = originals.get(row.path)
                    if not original:
                        continue
                    valid_splits = {
                        'reference': {'train', 'excluded'},
                        'holdout': {'validation', 'excluded'},
                        'excluded': {'excluded'},
                    }
                    if (
                        row.sha256 != original['sha256']
                        or row.size_bytes != original['size']
                        or (row.width, row.height) != (original['width'], original['height'])
                        or row.group_id != original['duplicate_group']
                        or row.split not in valid_splits[original['split']]
                        or 'r02_contact_sheet' not in row.exposure
                        or (original['used_as_input'] and 'inference_reference' not in row.exposure)
                    ):
                        issue('parent_study_record_changed', row)
    counts = Counter(r.split for r in dataset.images)
    if not counts['train']:
        issue('no_training_candidates')
    if not counts['validation']:
        issue('no_development_validation')
    if not counts['test']:
        warnings.append(dict(code='no_final_test_set', image_id=None))
    train_groups = Counter(r.group_id for r in dataset.images if r.split == 'train')
    for row in dataset.images:
        if row.split == 'test' and row.exposure:
            issue('final_test_previously_exposed', row)
        if row.split != 'train':
            continue
        if train_groups[row.group_id] > 1:
            issue('multiple_training_variants', row)
        if (
            row.caption.status != 'approved'
            or not row.caption.content.strip()
            or not row.caption.reviewed_by.strip()
        ):
            issue('caption_review_required', row)
        if (
            row.provenance.training_use != 'recorded'
            or not row.provenance.usage_note.strip()
            or not row.provenance.reviewed_by.strip()
        ):
            issue('source_use_record_required', row)
        if dataset.kind == 'character' and (
            row.identity != 'target' or row.character_ids != [dataset.subject_id]
        ):
            issue('target_character_review_required', row)
    return dict(
        schema_version=1,
        dataset_id=dataset.dataset_id,
        version=dataset.version,
        manifest_sha256=digest(canonical(dataset)),
        counts={k: counts[k] for k in ('train', 'validation', 'test', 'excluded')},
        unique_contents=len({r.sha256 for r in dataset.images}),
        issues=issues,
        warnings=warnings,
        data_ready=not issues,
        training_started=False,
    )


def audit(dataset, root, expected_base, study=None):
    report = audit_metadata(dataset, expected_base, study)
    for row in dataset.images:
        try:
            read_source(root, row.path, row)
        except (OSError, ValueError) as exc:
            report['issues'].append(dict(code='source_integrity', image_id=row.id, detail=str(exc)))
    report['data_ready'] = not report['issues']
    return report


def normalized(raw):
    with Image.open(io.BytesIO(raw)) as source:
        if (
            len(raw) > MAX_BYTES
            or source.width * source.height > MAX_PIXELS
            or getattr(source, 'n_frames', 1) != 1
        ):
            raise ValueError('原圖超過正規化限制')
        image = ImageOps.exif_transpose(source).convert('RGBA')
        rgb = Image.new('RGB', image.size, 'white')
        rgb.paste(image, mask=image.getchannel('A'))
        rgb.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
        rgb.info.clear()
        output = io.BytesIO()
        rgb.save(output, format='PNG')
        return output.getvalue(), rgb.size
