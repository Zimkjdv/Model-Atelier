"""Non-blocking process coordination for a running app and offline maintenance.

Locks live in the user's OS temp directory, never inside the inspected DATA.
Multiple lifespans in one process may share platform leases; maintenance may not.
"""
from contextlib import AbstractContextManager
import hashlib
import os
from pathlib import Path
import tempfile
import threading

_guard = threading.RLock()
_held = {}


class DataBusyError(RuntimeError):
    pass


def _lock(stream):
    stream.seek(0)
    if os.name == 'nt':
        import msvcrt
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(stream):
    stream.seek(0)
    if os.name == 'nt':
        import msvcrt
        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class DataLease(AbstractContextManager):
    def __init__(self, paths, *, maintenance=False):
        self.keys = sorted({os.path.normcase(str(Path(path).resolve())) for path in paths})
        self.maintenance = maintenance
        self.acquired = []

    def __enter__(self):
        with _guard:
            try:
                folder = Path(tempfile.gettempdir()).resolve() / 'model-atelier-data-locks'
                folder.mkdir(exist_ok=True)
                for key in self.keys:
                    if key in _held:
                        current = _held[key]
                        if self.maintenance or current['maintenance']:
                            raise DataBusyError('資料正在使用中；請先停止所有平台與資料寫入程序。')
                        current['count'] += 1
                    else:
                        name = hashlib.sha256(key.encode()).hexdigest() + '.lock'
                        stream = (folder / name).open('a+b')
                        try:
                            if stream.seek(0, 2) == 0:
                                stream.write(b'0'); stream.flush()
                            _lock(stream)
                        except OSError as exc:
                            stream.close()
                            raise DataBusyError('資料已被其他平台或維護程序使用；請先停機。') from exc
                        _held[key] = dict(stream=stream, count=1, maintenance=self.maintenance)
                    self.acquired.append(key)
            except BaseException:
                self.__exit__(None, None, None)
                raise
        return self

    def __exit__(self, *args):
        with _guard:
            for key in reversed(self.acquired):
                current = _held[key]
                current['count'] -= 1
                if not current['count']:
                    try:
                        _unlock(current['stream'])
                    finally:
                        current['stream'].close(); del _held[key]
            self.acquired.clear()
