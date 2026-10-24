"""Project-local exclusion between training and managed local dispatch.

The trainer owns the OS lease until its process exits. It must also verify that
the managed engine is stopped; this lease cannot control unrelated GPU clients.
"""

import asyncio
from contextlib import asynccontextmanager
import ipaddress
import json
import os
from pathlib import Path
import tempfile
import time
from urllib.parse import urlsplit

from backend.data_lease import DataBusyError, DataLease

MESSAGE = '本機訓練正在使用運算資源，新的生成尚未提交；訓練結束後再建立新任務。'


class ComputeBusy(RuntimeError):
    pass


def local_engine(url):
    try:
        host = urlsplit(url).hostname
        return host == 'localhost' or ipaddress.ip_address(host or '').is_loopback
    except ValueError:
        return False


def directory(root):
    return Path(root).resolve() / 'runtime' / 'training'


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent,
            prefix=path.name + '.',
            suffix='.tmp',
            mode='w',
            encoding='utf-8',
            delete=False,
        ) as stream:
            name = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if name is not None and name.exists():
            name.unlink()


def record(root):
    try:
        raw = (directory(root) / 'lease.json').read_bytes()
        if len(raw) > 8192:
            return {}
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


class Reservation:
    def __init__(self, root, kind, run_id=None):
        if kind not in ('training', 'inference'):
            raise ValueError('Unknown compute reservation')
        self.root, self.kind, self.run_id = Path(root).resolve(), kind, run_id
        self.lease = DataLease([directory(self.root)], maintenance=True)

    def __enter__(self):
        try:
            self.lease.__enter__()
        except DataBusyError as exc:
            raise ComputeBusy(MESSAGE) from exc
        try:
            atomic_json(
                directory(self.root) / 'lease.json',
                dict(kind=self.kind, run_id=self.run_id, pid=os.getpid()),
            )
        except BaseException:
            self.lease.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *args):
        return self.lease.__exit__(*args)


def status(root):
    try:
        with DataLease([directory(root)], maintenance=True):
            return dict(active=False, kind=None, run_id=None, pid=None)
    except DataBusyError:
        owner = record(root)
        return dict(
            active=True,
            kind=owner.get('kind', 'unknown'),
            run_id=owner.get('run_id'),
            pid=owner.get('pid'),
        )


def check_training(root, url):
    if local_engine(url):
        current = status(root)
        if current['active'] and current['kind'] == 'training':
            raise ComputeBusy(MESSAGE)


@asynccontextmanager
async def dispatch(root, url, *, timeout=15):
    if not local_engine(url):
        yield
        return
    deadline = time.monotonic() + timeout
    while True:
        reservation = Reservation(root, 'inference')
        try:
            reservation.__enter__()
            break
        except ComputeBusy:
            if record(root).get('kind') != 'inference' or time.monotonic() >= deadline:
                raise
            await asyncio.sleep(0.05)
    try:
        yield
    finally:
        reservation.__exit__(None, None, None)
