"""Deterministic synthetic records; callers must supply a fresh test database."""
import json
import sqlite3
from contextlib import closing
from uuid import NAMESPACE_URL, uuid5


def seed(context, count):
    rows = []
    for i in range(count):
        identity = str(uuid5(NAMESPACE_URL, f'atelier-listing:{i}'))
        stamp = f'2026-01-{1 + i % 28:02d}T12:00:{i % 60:02d}+00:00'
        graph = {'5': {'class_type': 'KSampler', 'inputs': {'seed': 18446744073709551615}},
                 'fixture': {'class_type': 'Fixture', 'inputs': {'padding': 'x' * 4096}}}
        common = dict(id=identity, title=f'fixture-{i:05d}.png', checkpoint=f'model-{i % 5}.safetensors',
                      model_version='fixture-v1', created_at=stamp, workflow=graph, engine_url='http://mock-engine.invalid:8188',
                      revision=0, workflow_id=None, lora_metadata=[], runtime_metadata={'fixture': 'x' * 1024})
        artwork = dict(common, job_id=identity, prompt_id=identity, imported_at=stamp, favorite=i % 3 == 0, archived=i % 7 == 0,
                       notes='synthetic note', parameters=dict(prompt='fixture forest', negative_prompt='', seed='18446744073709551615', steps=20, cfg=7, sampler='euler', scheduler='normal', denoise=1),
                       ratings=dict(prompt_adherence=None, character_consistency=None, visual_style=None, composition=None),
                       width=64, height=64, size=128, extension='png', media_type='image/png', sha256='0' * 64)
        job = dict(common, status='completed', prompt_id=identity, history={'fixture': 'x' * 2048}, error=None)
        asset = dict(id=identity, title=f'asset-{i:05d}.png', width=64, height=64, size=128, sha256='0' * 64,
                     created_at=stamp, archived=i % 7 == 0, purpose='composition', revision=0,
                     preprocessing={'fixture': 'x' * 1024})
        rows.extend((('artwork:' + identity, json.dumps(artwork)), ('job:' + identity, json.dumps(job)), ('asset:' + identity, json.dumps(asset))))
    with closing(sqlite3.connect(context.DB)) as db, db:
        db.executemany('INSERT OR REPLACE INTO settings VALUES (?, ?)', rows)
