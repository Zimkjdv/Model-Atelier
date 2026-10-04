"""The standard checkpoint template and conservative, lossless restoration."""

ROLES = ('loader', 'positive', 'negative', 'latent', 'sampler', 'decoder', 'output')


def build(value, node_ids=None):
    node_ids = node_ids or dict(zip(ROLES, map(str, range(1, 8))))
    loader, positive, negative, latent, sampler, decoder, output = (node_ids[role] for role in ROLES)
    result = {
        loader: {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': value['checkpoint']}},
        positive: {'class_type': 'CLIPTextEncode', 'inputs': {'text': value['prompt'], 'clip': [loader, 1]}},
        negative: {'class_type': 'CLIPTextEncode', 'inputs': {'text': value['negative_prompt'], 'clip': [loader, 1]}},
        latent: {'class_type': 'EmptyLatentImage', 'inputs': {'width': value['width'], 'height': value['height'], 'batch_size': 1}},
        sampler: {'class_type': 'KSampler', 'inputs': {
            'model': [loader, 0], 'positive': [positive, 0], 'negative': [negative, 0], 'latent_image': [latent, 0],
            'seed': int(value['seed']), 'steps': value['steps'], 'cfg': value['cfg'],
            'sampler_name': value['sampler_name'], 'scheduler': value['scheduler'], 'denoise': value['denoise']}},
        decoder: {'class_type': 'VAEDecode', 'inputs': {'samples': [sampler, 0], 'vae': [loader, 2]}},
        output: {'class_type': 'SaveImage', 'inputs': {'images': [decoder, 0], 'filename_prefix': 'ModelAtelier'}},
    }
    active = [item for item in value.get('loras', []) if item['enabled']]
    if len(active) > 1:
        raise ValueError('目前僅支援單一 LoRA')
    if active:
        lora = node_ids.get('lora', '8')
        if lora in result:
            raise ValueError('LoRA 節點 ID 重複')
        choice = active[0]
        result[lora] = dict(class_type='LoraLoader', inputs=dict(
            model=[loader, 0], clip=[loader, 1], lora_name=choice['name'],
            strength_model=choice['strength_model'], strength_clip=choice['strength_clip']))
        result[sampler]['inputs']['model'] = [lora, 0]
        for node in (positive, negative):
            result[node]['inputs']['clip'] = [lora, 1]
    return result


def extract(artwork, validate, *, allow_lora=False):
    """Restore only a whole template; extra inputs or branches cannot be dropped."""
    message = '此作品工作流程無法完整還原到目前創作表單，請下載原工作流程使用；未載入任何參數'
    try:
        workflow = artwork['workflow']
        if not isinstance(workflow, dict) or len(workflow) not in ((7, 8) if allow_lora else (7,)):
            raise ValueError(message)
        by_kind = {}
        for node_id, node in workflow.items():
            if not isinstance(node_id, str) or not isinstance(node, dict) or set(node) - {'class_type', 'inputs', '_meta'}:
                raise ValueError(message)
            if not isinstance(node.get('inputs'), dict):
                raise ValueError(message)
            by_kind.setdefault(node.get('class_type'), []).append(node_id)
        def one(kind):
            entries = by_kind.get(kind, [])
            if len(entries) != 1:
                raise ValueError(message)
            return entries[0]
        node_ids = dict(loader=one('CheckpointLoaderSimple'), latent=one('EmptyLatentImage'),
                        sampler=one('KSampler'), decoder=one('VAEDecode'), output=one('SaveImage'))
        choices = []
        if len(workflow) == 8:
            node_ids['lora'] = one('LoraLoader')
            inputs = workflow[node_ids['lora']]['inputs']
            choices = [dict(name=inputs['lora_name'], enabled=True,
                            strength_model=inputs['strength_model'], strength_clip=inputs['strength_clip'])]
        if node_ids['output'] != artwork['source']['node_id'] or len(by_kind.get('CLIPTextEncode', [])) != 2:
            raise ValueError(message)
        sampler = workflow[node_ids['sampler']]['inputs']
        for role in ('positive', 'negative'):
            link = sampler[role]
            if (not isinstance(link, list) or len(link) != 2 or not isinstance(link[0], str)
                    or type(link[1]) is not int or link[1] != 0
                    or link[0] not in by_kind['CLIPTextEncode']):
                raise ValueError(message)
            node_ids[role] = link[0]
        if len(set(node_ids.values())) != len(workflow) or type(sampler['seed']) is not int:
            raise ValueError(message)
        latent = workflow[node_ids['latent']]['inputs']
        if type(latent['batch_size']) is not int or latent['batch_size'] != 1:
            raise ValueError(message)
        settings = validate(dict(
            title=artwork['title'][:100], prompt=workflow[node_ids['positive']]['inputs']['text'],
            negative_prompt=workflow[node_ids['negative']]['inputs']['text'], engine_url=artwork['engine_url'],
            checkpoint=workflow[node_ids['loader']]['inputs']['ckpt_name'], width=latent['width'], height=latent['height'],
            seed=str(sampler['seed']), steps=sampler['steps'], cfg=sampler['cfg'],
            sampler_name=sampler['sampler_name'], scheduler=sampler['scheduler'], denoise=sampler['denoise'], reference_ids=[], loras=choices))
        if not settings['checkpoint'] or settings['checkpoint'] != artwork['checkpoint']:
            raise ValueError(message)
        expected = build(settings, node_ids)
        for node_id, node in workflow.items():
            # _meta contains display labels and does not change node execution.
            if {key: value for key, value in node.items() if key != '_meta'} != expected[node_id]:
                raise ValueError(message)
            for value in node['inputs'].values():
                if isinstance(value, list) and (len(value) != 2 or type(value[1]) is not int):
                    raise ValueError(message)
        return settings
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ValueError(message) from exc
