from typing import Literal
from fastapi import HTTPException, Query
from backend.listing import Pager, ListingError


def install(app, host):
    pager = Pager(host.DB)

    @app.get('/api/library/{kind}')
    def page(
        kind: Literal['artworks', 'jobs', 'assets'],
        limit: int = Query(40, ge=1, le=100),
        cursor: str | None = Query(None, max_length=80),
        q: str = Query('', max_length=200),
        scope: Literal['active', 'archived', 'all'] = 'active',
        favorites_only: bool = False,
        model: str = Query('', max_length=2048),
        status: str = Query('', max_length=30),
        workflow: Literal[
            'all', 'checkpoint', 'flux', 'flux-addon', 'inpaint', 'control', 'reference'
        ] = 'all',
        purpose: Literal['', 'unspecified', 'style', 'character', 'composition'] = '',
        sort: Literal['latest', 'oldest', 'rating', 'model'] = 'latest',
    ):
        try:
            result = pager.page(
                kind,
                limit=limit,
                cursor=cursor,
                q=q,
                scope=scope,
                favorites_only=favorites_only,
                model=model,
                status=status,
                workflow=workflow,
                purpose=purpose,
                sort=sort,
            )
        except ListingError as exc:
            raise HTTPException(exc.status, str(exc))
        if kind == 'artworks':
            folder = host.DATA / 'artworks'
            for item in result['items']:
                item['image_available'] = (
                    folder / (item['id'] + '.' + item['extension'])
                ).is_file()
                item['thumbnail_available'] = (folder / (item['id'] + '.thumb.png')).is_file()
        return result
