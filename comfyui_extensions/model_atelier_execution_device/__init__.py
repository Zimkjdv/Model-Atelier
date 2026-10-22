"""Model Atelier's first-party, read-only ComfyUI device report (no graph nodes)."""
import asyncio
from uuid import UUID

from aiohttp import web
from server import PromptServer
import comfy.model_management as management

from .probe import collect

NODE_CLASS_MAPPINGS = {}


@PromptServer.instance.routes.get('/model_atelier/execution-device')
async def execution_device(request):
    probe_id = request.query.get('probe_id', '')
    try:
        if str(UUID(probe_id)) != probe_id or set(request.query) != {'probe_id'}:
            raise ValueError('invalid nonce')
    except ValueError:
        return web.json_response({'error': 'A canonical probe_id UUID is required'}, status=400)
    report = await asyncio.to_thread(collect, management, probe_id)
    return web.json_response(report, headers={'Cache-Control': 'no-store'})
