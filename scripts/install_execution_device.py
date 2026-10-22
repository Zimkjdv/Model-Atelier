"""Install only the bundled first-party report into the managed ComfyUI."""
from pathlib import Path
import os
import tempfile


def install(workspace):
    root = Path(workspace).resolve()
    engine = root / 'runtime' / 'ComfyUI'
    source = root / 'comfyui_extensions' / 'model_atelier_execution_device'
    target = engine / 'custom_nodes' / 'model_atelier_execution_device'
    # Never follow a redirected runtime/custom_nodes into another checkout.
    for path in (root / 'runtime', engine, engine / 'custom_nodes', target):
        if path.is_symlink() or path.resolve() != path:
            raise ValueError('Managed ComfyUI extension path must not be redirected')
    content = {name: (source / name).read_bytes() for name in ('__init__.py', 'probe.py')}
    target.mkdir(parents=True, exist_ok=True)
    for name, raw in content.items():
        destination = target / name
        if destination.is_symlink():
            raise ValueError('Managed extension file must not be a symbolic link')
        if destination.is_file() and destination.read_bytes() == raw:
            continue
        descriptor, temporary = tempfile.mkstemp(prefix='.atelier-', dir=target)
        try:
            with os.fdopen(descriptor, 'wb') as handle:
                handle.write(raw)
            os.replace(temporary, destination)
        finally:
            Path(temporary).unlink(missing_ok=True)
    return target


if __name__ == '__main__':
    print(install(Path(__file__).resolve().parents[1]))
