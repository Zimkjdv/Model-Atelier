"""Synthetic R03 browser registration, isolated from all production data."""

from backend import fooocus_workflows as flow, catalog

NODES = {
    'INPAINT_LoadFooocusInpaint': dict(
        input=dict(
            required={
                k: ['COMBO', dict(options=[w['filename'] for w in flow.WEIGHTS])]
                for k in ('head', 'patch')
            }
        ),
        output=['INPAINT_PATCH'],
    ),
    'INPAINT_ApplyFooocusInpaint': dict(
        input=dict(required=dict(model=['MODEL'], patch=['INPAINT_PATCH'], latent=['LATENT'])),
        output=['MODEL'],
    ),
}


def install(wrapper, context, state, engine):
    @wrapper.post('/qa/fooocus/{mode}')
    def enable(mode: str):
        state['fooocus'] = mode == 'enable'
        if state['fooocus']:
            names = [
                m['name'] for m in catalog.read(context.DB, engine)['models'] if m['listed']
            ] + [flow.BASE['filename']]
            catalog.merge(context.DB, engine, names)
            catalog.update_metadata(
                context.DB,
                engine,
                flow.BASE['filename'],
                dict(
                    architecture='sdxl',
                    sha256=flow.BASE['sha256'],
                    size_bytes=flow.BASE['size_bytes'],
                ),
            )
        else:
            catalog.mutate(
                context.DB,
                engine,
                lambda v: v.update(
                    models=[m for m in v['models'] if m['name'] != flow.BASE['filename']]
                ),
            )
        return dict(ok=True)
