"""Read the running engine's configured device; no tensors, models or fallback."""
import re


def collect(management, probe_id):
    report = dict(schema_version=1, producer='model-atelier-execution-device-v1', probe_id=probe_id,
                  status='unknown', reason='probe_failed', device=None, backend_available=None)
    select = getattr(management, 'get_torch_device', None)
    if not callable(select):
        return report
    try:
        device = select()
    except (RuntimeError, AssertionError):
        # This is the same device selection used by the current engine, not a
        # guess based on an empty GPU list or a local CUDA diagnostic.
        return report | dict(status='unavailable', reason='device_selection_failed')
    except Exception:
        return report
    kind, index = getattr(device, 'type', None), getattr(device, 'index', None)
    if (not isinstance(kind, str) or re.fullmatch(r'[a-z][a-z0-9_]{0,39}', kind) is None
            or (index is not None and (type(index) is not int or not 0 <= index <= 65535))):
        return report
    report['device'] = dict(type=kind, index=index)
    try:
        torch = management.torch
        backend = getattr(torch.backends, 'mps', None) if kind == 'mps' else getattr(torch, kind, None)
        check = getattr(backend, 'is_available', None) if kind in {'cuda', 'mps', 'xpu', 'npu', 'mlu'} else None
        if callable(check):
            available = check()
            if type(available) is not bool:
                return report
            report['backend_available'] = available
            if not available:
                return report | dict(status='unavailable', reason='backend_unavailable')
        return report | dict(status='available', reason='device_selected')
    except Exception:
        # An incomplete backend query does not prove there is no usable device.
        return report
