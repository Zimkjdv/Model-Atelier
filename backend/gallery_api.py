"""Only import filenames recorded by a successful, platform-owned job."""
import asyncio
import json
from uuid import UUID

import httpx
from fastapi import HTTPException, Response
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from backend import gallery, jobs, catalog, workflows


def install(app, host):
    import_lock = asyncio.Lock()

    def lookup(artwork_id):
        try:
            return gallery.get(host.DB, str(artwork_id))
        except KeyError:
            raise HTTPException(404, '找不到作品')

    def summary(item):
        value = {k: v for k, v in item.items() if k != 'workflow'}
        folder = host.DATA / 'artworks'
        value['image_available'] = (folder / (item['id'] + '.' + item['extension'])).is_file()
        value['thumbnail_available'] = (folder / (item['id'] + '.thumb.png')).is_file()
        return value

    @app.get('/api/artworks')
    def list_artworks():
        return [summary(item) for item in gallery.list_all(host.DB)]

    @app.get('/api/artworks/{artwork_id}')
    def detail(artwork_id: UUID):
        return summary(lookup(artwork_id))

    @app.get('/api/artworks/{artwork_id}/workflow')
    def workflow(artwork_id: UUID):
        return Response(json.dumps(lookup(artwork_id)['workflow'], ensure_ascii=False, indent=2), media_type='application/json',
                        headers={'Content-Disposition': f'attachment; filename="{artwork_id}.json"'})

    @app.get('/api/artworks/{artwork_id}/creation-settings')
    def creation_settings(artwork_id: UUID):
        item = lookup(artwork_id)
        def validate(value):
            return host.DraftInput.model_validate(value).model_dump(mode='json', exclude={'revision'})
        try:
            settings = workflows.extract(item, validate)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        original = catalog.read(host.DB, settings['engine_url'])
        model = next((value for value in original['models'] if value['name'] == settings['checkpoint']), None)
        matches = settings['engine_url'] == host.engine_url()
        checkpoint_status = ('unknown' if original.get('synced_at') is None or original.get('sync_error')
                             else 'available' if model and model.get('listed') else 'missing')
        warnings = []
        if not matches:
            warnings.append('作品原引擎與目前設定不同；已保留原位址，生成前請先確認引擎設定')
        if checkpoint_status == 'missing':
            warnings.append('原 checkpoint 不在最近同步的模型清單；請先安裝模型或重新同步後確認')
        elif checkpoint_status == 'unknown':
            warnings.append('原引擎模型清單尚未同步或同步失敗；checkpoint 可用性待確認')
        else:
            warnings.append('checkpoint 僅在最近同步清單中，實際可用性將於生成前再次檢查')
        version = item.get('model_version') or '未知'
        if version == '未知':
            warnings.append('原作品模型版本未知，無法確認目前 checkpoint 與原版本一致')
        elif model and model.get('version') and model['version'] != version:
            warnings.append('目前登記的模型版本與原作品不同；已保留原作品版本供比較')
        return dict(artwork_id=str(artwork_id), settings=settings, model_version=version, warnings=warnings,
                    availability=dict(current_engine_url=host.engine_url(), engine_matches=matches,
                                      checkpoint_status=checkpoint_status, catalog_synced_at=original.get('synced_at')))

    @app.get('/api/artworks/{artwork_id}/image')
    def image(artwork_id: UUID, download: bool = False, thumbnail: bool = False):
        item = lookup(artwork_id)
        extension = 'thumb.png' if thumbnail else item['extension']
        target = host.DATA / 'artworks' / (str(artwork_id) + '.' + extension)
        if not target.is_file():
            raise HTTPException(404, '作品檔案已遺失，請從備份還原；生成參數仍保留')
        return FileResponse(target, media_type='image/png' if thumbnail else item['media_type'],
                            filename=target.name if download else None,
                            headers={'X-Content-Type-Options': 'nosniff'})

    @app.post('/api/jobs/{job_id}/artworks')
    async def import_outputs(job_id: UUID):
        async with import_lock:
            try:
                job = jobs.get(host.DB, str(job_id))
            except KeyError:
                raise HTTPException(404, '找不到任務')
            try:
                sources = gallery.outputs(job)
            except ValueError as exc:
                raise HTTPException(409, str(exc))
            imported, existing, errors = [], [], []
            async with httpx.AsyncClient(timeout=30, trust_env=False, follow_redirects=False) as client:
                for source in sources:
                    artwork_id = gallery.output_id(job, source)
                    try:
                        item = gallery.get(host.DB, artwork_id)
                    except KeyError:
                        item = None
                    if item:
                        existing.append(summary(item))
                        continue
                    try:
                        params = {k: source[k] for k in ('filename', 'subfolder', 'type')}
                        async with client.stream('GET', job['engine_url'] + '/view', params=params) as response:
                            if response.status_code == 404:
                                raise ValueError('ComfyUI 輸出檔案已遺失')
                            response.raise_for_status()
                            raw = bytearray()
                            async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                                if len(raw) + len(chunk) > gallery.MAX_BYTES:
                                    raise ValueError('單張作品不可超過 32 MiB')
                                raw.extend(chunk)
                        item, created = await run_in_threadpool(gallery.save, host.DB, host.DATA / 'artworks', job, source, bytes(raw))
                        (imported if created else existing).append(summary(item))
                    except httpx.HTTPStatusError:
                        errors.append(dict(source=source, message='ComfyUI 無法提供圖片，請確認原引擎與輸出檔案'))
                    except httpx.RequestError:
                        errors.append(dict(source=source, message='原 ComfyUI 引擎離線或下載逾時，請稍後重試匯入'))
                    except ValueError as exc:
                        errors.append(dict(source=source, message=str(exc)))
                    except OSError:
                        errors.append(dict(source=source, message='本機保存失敗，請檢查磁碟空間與寫入權限'))
            return dict(imported=imported, existing=existing, errors=errors)
