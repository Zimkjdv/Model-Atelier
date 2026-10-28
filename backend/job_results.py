"""Read-only, bounded previews of recorded successful job outputs; never import."""

from uuid import UUID

import httpx
from fastapi import HTTPException, Response
from starlette.concurrency import run_in_threadpool

from backend import gallery, jobs


def install(app, host):
    def lookup(identifier):
        try:
            job = jobs.get(host.DB, str(identifier))
        except KeyError as exc:
            raise HTTPException(404, '找不到原任務') from exc
        try:
            return job, gallery.outputs(job)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    def saved(job, source):
        try:
            item = gallery.get(host.DB, gallery.output_id(job, source))
        except KeyError:
            return None
        return item

    def local_path(item):
        return host.DATA / 'artworks' / (item['id'] + '.' + item['extension'])

    @app.get('/api/jobs/{job_id}/results')
    def results(job_id: UUID):
        job, sources = lookup(job_id)
        items = []
        for index, source in enumerate(sources):
            item = saved(job, source)
            items.append(
                dict(
                    index=index,
                    filename=source['filename'],
                    saved=bool(item),
                    local_available=bool(item and local_path(item).is_file()),
                    width=item['width'] if item else None,
                    height=item['height'] if item else None,
                )
            )
        return dict(job_id=job['id'], items=items)

    @app.get('/api/jobs/{job_id}/results/{index}/image')
    async def image(job_id: UUID, index: int):
        job, sources = await run_in_threadpool(lookup, job_id)
        if not 0 <= index < len(sources):
            raise HTTPException(404, '找不到此任務輸出')
        source = sources[index]
        item = await run_in_threadpool(saved, job, source)
        if item and local_path(item).is_file():
            from fastapi.responses import FileResponse

            return FileResponse(
                host.DATA / 'artworks' / (item['id'] + '.' + item['extension']),
                media_type=item['media_type'],
                headers={'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'no-store'},
            )
        try:
            async with host.http_client(
                timeout=30, trust_env=False, follow_redirects=False
            ) as client:
                async with client.stream(
                    'GET',
                    job['engine_url'] + '/view',
                    params={k: source[k] for k in ('filename', 'subfolder', 'type')},
                ) as response:
                    if response.status_code == 404:
                        raise HTTPException(404, '原引擎結果圖片已遺失；不會重新生成。')
                    response.raise_for_status()
                    raw = bytearray()
                    async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                        if len(raw) + len(chunk) > gallery.MAX_BYTES:
                            raise ValueError('結果圖片超過 32 MiB')
                        raw.extend(chunk)
            _, media_type, _, _, _ = await run_in_threadpool(gallery.decode, bytes(raw))
        except httpx.HTTPError as exc:
            raise HTTPException(
                502, '原引擎離線或無法讀取結果；尚未匯入作品庫的圖片需要原引擎。'
            ) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return Response(
            bytes(raw),
            media_type=media_type,
            headers={'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'no-store'},
        )
