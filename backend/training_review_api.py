"""Local-only human review endpoints; never launch a trainer or generate images."""

from typing import Literal
from uuid import UUID
from fastapi import HTTPException, Query, Response
from pydantic import Field
from backend import training_data as data
from backend.training_review import Reviews, Conflict


class Import(data.Contract):
    request_id: str = Field(pattern=r'^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$')
    source_root: str = Field(min_length=1, max_length=2048)
    manifest_json: str = Field(max_length=data.MAX_MANIFEST_BYTES)
    study_json: str = Field(default='', max_length=data.MAX_MANIFEST_BYTES)


class Edit(data.Contract):
    id: str
    group_id: str
    split: Literal['train', 'validation', 'test', 'excluded']
    exclusion_reason: str = ''
    exposure: list[
        Literal[
            'r02_contact_sheet', 'inference_reference', 'tuning', 'training', 'final_evaluation'
        ]
    ]
    identity: Literal['unreviewed', 'target', 'other', 'mixed']
    character_ids: list[str]
    caption: data.Caption
    provenance: data.Provenance


class Save(data.Contract):
    revision: int = Field(ge=1, le=100)
    version: str = Field(pattern=r'^[a-z0-9][a-z0-9_.-]{0,79}$')
    images: list[Edit] = Field(max_length=10000)


class Export(data.Contract):
    request_id: str = Field(pattern=r'^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$')
    revision: int = Field(ge=1, le=100)


def install(app, host):
    service = Reviews(host)

    def call(method, *args):
        try:
            service.native()
            return method(*args)
        except Conflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        except (ValueError, OSError) as exc:
            raise HTTPException(400, str(exc)[:2000]) from exc

    @app.get('/api/training/datasets')
    def listing():
        return dict(
            available=host.deployment.kind == 'native',
            datasets=call(service.listing) if host.deployment.kind == 'native' else [],
        )

    @app.post('/api/training/datasets', status_code=201)
    def importing(value: Import):
        return call(service.create, value)

    @app.get('/api/training/datasets/{uid}')
    def detail(uid: UUID, revision: int | None = Query(default=None, ge=1, le=100)):
        return call(service.get, uid, revision)

    @app.put('/api/training/datasets/{uid}')
    def save(uid: UUID, value: Save):
        return call(service.save, uid, value)

    @app.post('/api/training/datasets/{uid}/check')
    def check(uid: UUID):
        return call(service.check, uid)

    @app.get('/api/training/datasets/{uid}/manifest')
    def manifest(uid: UUID, revision: int | None = Query(default=None, ge=1, le=100)):
        value = call(service.get, uid, revision)
        return Response(
            data.manifest_bytes(data.Dataset.model_validate(value['dataset'])),
            media_type='application/json',
            headers={
                'Content-Disposition': f'attachment; filename="dataset-r{value["revision"]}.json"'
            },
        )

    @app.get('/api/training/datasets/{uid}/images/{image_id}')
    def image(uid: UUID, image_id: str, revision: int = Query(ge=1, le=100)):
        return Response(
            call(service.thumbnail, uid, image_id, revision),
            media_type='image/png',
            headers={'Cache-Control': 'no-store'},
        )

    @app.post('/api/training/datasets/{uid}/exports')
    def export(uid: UUID, value: Export):
        return call(service.export, uid, value)

    @app.get('/api/training/exports/{uid}')
    def export_status(uid: UUID):
        return call(service.export_status, uid)
