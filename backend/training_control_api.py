"""Explicit Windows training actions. GETs and prepare never start a trainer."""

from typing import Literal
from uuid import UUID
from fastapi import HTTPException, Request
import httpx
from pydantic import Field
from backend import training_data as data, training_runs as runs, training_control
from backend.training_control import Control
from backend.training_review import Conflict
from backend import training_artifacts as artifacts
from backend import compute_lease

UUID_PATTERN = r'^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$'


class Prepare(data.Contract):
    request_id: str = Field(pattern=UUID_PATTERN)
    export_id: str = Field(pattern=UUID_PATTERN)
    label: str = Field(min_length=1, max_length=120)
    purpose: Literal['technical-smoke', 'development-training'] = 'development-training'
    gpu_index: int = Field(default=0, ge=0, le=15)
    resolution: Literal[512, 1024] = 1024
    rank: Literal[4, 8, 16] = 4
    learning_rate: float = Field(default=0.0001, gt=0, le=0.01, allow_inf_nan=False)
    max_steps: int = Field(ge=1, le=10000)
    save_every_steps: int = Field(default=100, ge=1, le=10000)
    seed: int = Field(default=42, ge=0, le=4294967295)


class Resume(data.Contract):
    request_id: str = Field(pattern=UUID_PATTERN)
    resume_run_id: str = Field(pattern=UUID_PATTERN)
    checkpoint: str = Field(pattern=r'^step-[1-9][0-9]{0,7}$')


class Import(data.Contract):
    run_id: str = Field(pattern=UUID_PATTERN)


class Evaluation(Import):
    request_id: str = Field(pattern=UUID_PATTERN)
    action: Literal['evaluation'] = 'evaluation'


def install(app, host):
    service = Control(host)
    host.training_control = service

    def call(method, *args, **kwargs):
        try:
            service.native()
            return method(*args, **kwargs)
        except Conflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except (KeyError, FileNotFoundError) as exc:
            raise HTTPException(404, str(exc)[:1000]) from exc
        except (ValueError, OSError) as exc:
            raise HTTPException(400, str(exc)[:2000]) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(
                502, '本機模型庫操作未完成；請確認原生引擎與模型登記，再明確操作。'
            ) from exc

    def origin(request):
        # Use the actual listener, never a client-provided Host or URL.
        return 'http://127.0.0.1:' + str(request.scope['server'][1])

    @app.get('/api/training/control')
    def listing():
        if not training_control.supported(host):
            return dict(available=False, requests=[], runs=[], exports=[])
        links = service.records('training_run_link:')
        results = []
        for link in links:
            try:
                value = service.detail(link['run_id'])
                results.append(
                    {
                        k: value[k]
                        for k in ('run_id', 'status', 'resources_released', 'configuration')
                    }
                )
            except (OSError, ValueError, KeyError):
                results.append(
                    dict(
                        run_id=link['run_id'],
                        status='unavailable',
                        resources_released=None,
                        configuration=dict(label='原 run 暫不可讀，請保留資料檢查'),
                    )
                )
        return dict(
            available=True,
            requests=[
                service.request(v['request_id']) for v in service.records('training_request:')
            ],
            runs=results,
            exports=service.exports(),
        )

    @app.post('/api/training/runtime/check')
    def environment():
        return call(runs.environment.check, host.ROOT)

    @app.post('/api/training/requests', status_code=202)
    def prepare(value: Prepare):
        return call(service.begin, value)

    @app.post('/api/training/resume-requests', status_code=202)
    def resume(value: Resume):
        return call(service.begin, value)

    @app.get('/api/training/requests/{uid}')
    def request(uid: UUID):
        return call(service.request, uid)

    @app.post('/api/training/runs/import')
    def importing(value: Import):
        return call(service.link, value.run_id)

    @app.get('/api/training/runs/{uid}')
    def detail(uid: UUID):
        return call(service.detail, uid)

    @app.post('/api/training/runs/{uid}/start', status_code=202)
    def start(uid: UUID):
        return call(service.start, uid)

    @app.post('/api/training/runs/{uid}/stop')
    def stop(uid: UUID):
        call(service.detail, uid)
        return call(runs.stop, str(uid), root=host.ROOT)

    @app.post('/api/training/runs/{uid}/artifact')
    def install_artifact(uid: UUID):
        call(service.detail, uid)
        return call(artifacts.register, str(uid), root=host.ROOT)

    @app.post('/api/training/runs/{uid}/publish')
    def publish(uid: UUID, request: Request):
        call(service.detail, uid)
        lease = compute_lease.status(host.ROOT)
        if lease['active'] and lease.get('kind') == 'training':
            raise HTTPException(409, '先等待所有本機訓練釋放資源，再恢復引擎並同步模型庫。')
        with httpx.Client(base_url=origin(request), timeout=30, trust_env=False) as client:
            return call(artifacts.publish, client, str(uid), root=host.ROOT)

    @app.post('/api/training/evaluation-requests', status_code=202)
    def evaluation(value: Evaluation, request: Request):
        return call(service.begin, value, origin(request))
