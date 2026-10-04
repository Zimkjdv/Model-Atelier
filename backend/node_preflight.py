"""Check standard node registration before dispatch, never infer GPU readiness."""
import asyncio


class MissingNodes(ValueError):
    pass


async def check(client, engine_url, workflow, *, checked=()):
    # CheckpointLoaderSimple and KSampler are checked by existing live validation.
    names = sorted({node['class_type'] for node in workflow.values()} - {'CheckpointLoaderSimple', 'KSampler'} - set(checked))

    async def inspect(name):
        response = await client.get(engine_url + '/object_info/' + name)
        response.raise_for_status()
        if len(response.content) > 1024 * 1024:
            raise ValueError('節點回應過大')
        value = response.json()
        if not isinstance(value, dict):
            raise ValueError('節點清單格式無效')
        if name not in value:
            return name
        definition = value[name]
        if (not isinstance(definition, dict) or not isinstance(definition.get('input'), dict)
                or not isinstance(definition['input'].get('required'), dict)):
            raise ValueError('節點定義格式無效')
        return None

    # Await every request before closing the HTTP client, including failures.
    results = await asyncio.gather(*(inspect(name) for name in names), return_exceptions=True)
    for value in results:
        if isinstance(value, BaseException):
            raise value
    missing = [value for value in results if value is not None]
    if missing:
        raise MissingNodes('ComfyUI 缺少必要節點：' + '、'.join(missing) + '；尚未提交任務')
