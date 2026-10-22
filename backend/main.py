"""Application factory. Importing this module never creates user data."""
import csv
import io
import math
import os
from pathlib import Path
import subprocess
from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from backend import environment, core_api, submissions, gallery_api, model_profiles, model_paths
from backend import validation_records, generation_advice, storage, loras, lora_compatibility, lora_validation
from backend import flux_plan, flux_catalog, settings_transfer, stack_validation, experiment_plans
from backend.schemas import Settings, ModelTarget, ModelMetadata, DraftInput, AssetUpdate
from backend.app_context import AppContext

ROOT = Path(__file__).resolve().parents[1]


def gpu_info():
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=index,name,memory.total,memory.used,memory.free,driver_version', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )
        if result.returncode:
            return [], '無法取得 NVIDIA 資訊，請檢查驅動與裝置狀態'
        cards = []
        for row in csv.reader(io.StringIO(result.stdout), skipinitialspace=True):
            if len(row) != 6:
                continue
            def memory(value):
                try:
                    amount = float(value)
                    return int(amount * 1024 * 1024) if math.isfinite(amount) and amount >= 0 and amount * 1024 * 1024 <= environment.MAX_NUMBER else None
                except (ValueError, OverflowError):
                    return None
            total, used, free = (memory(value) for value in row[2:5])
            total = total if total is not None and total > 0 else None
            used = used if used is not None and (total is None or used <= total) else None
            free = free if free is not None and (total is None or free <= total) else None
            cards.append(dict(index=row[0], name=environment.text(row[1]), total=total, used=used, free=free,
                              driver=environment.text(row[5], 80)))
        return cards, None if cards else '未偵測到 NVIDIA GPU'
    except (OSError, subprocess.TimeoutExpired):
        return [], '無法取得 NVIDIA 資訊：nvidia-smi 不可用或查詢逾時'


def create_app(*, data_root: str | Path | None = None, database: str | Path | None = None,
               root: str | Path | None = None, engine_client_factory=None):
    """Build isolated routes; initialize SQLite only when ASGI lifespan starts.

    root selects managed runtime/static files, data_root selects persistent
    images, and database defaults to data_root/atelier.sqlite3. The optional
    engine client factory receives the existing httpx keyword options.
    """
    workspace = Path(root).resolve() if root is not None else ROOT
    data = Path(data_root).resolve() if data_root is not None else workspace / 'data'
    db = Path(database).resolve() if database is not None else data / 'atelier.sqlite3'
    context = AppContext(workspace, data, db, engine_client_factory, gpu_info)

    @asynccontextmanager
    async def lifespan(app):
        context.initialize()
        yield

    app = FastAPI(title='Model Atelier', version='0.1.0', lifespan=lifespan)
    app.state.context = context
    core_api.install(app, context)
    checkpoint_submissions = submissions.install(app, context)
    from backend import inpaint_api
    inpaint_submissions=inpaint_api.install(app, context, checkpoint_submissions)
    from backend import inpaint_feather_api
    inpaint_feather_api.install(app,context,inpaint_submissions)
    from backend import control_api, control_catalog
    control_catalog.install(app,context)
    control_api.install(app,context,checkpoint_submissions)
    from backend import canny_preview
    canny_preview.install(app,context)
    from backend import control_edges_api
    control_edges_api.install(app,context)
    gallery_api.install(app, context)
    model_profiles.install(app, context)
    model_paths.install(app, context)
    environment.install(app, context)
    validation_records.install(app, context)
    generation_advice.install(app, context)
    storage.install(app, context)
    loras.install(app, context)
    lora_compatibility.install(app, context)
    lora_validation.install(app, context)
    flux_plan.install(app, context)
    flux_catalog.install(app, context)
    settings_transfer.install(app, context)
    stack_validation.install(app, context)
    experiment_plans.install(app, context)


    frontend = workspace / 'frontend' / 'dist'
    if frontend.is_dir():
        app.mount('/', StaticFiles(directory=frontend, html=True), name='frontend')
    return app


app = create_app()
