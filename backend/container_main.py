"""Optional Linux-container entry point; native launchers never read these options."""

import os
from pathlib import Path
import socket
import struct
import sys

from backend.deployment_profile import Profile


def bridge_gateway(path=Path('/proc/net/route')):
    for line in path.read_text(encoding='ascii').splitlines()[1:]:
        fields = line.split()
        if len(fields) >= 4 and fields[1] == '00000000' and int(fields[3], 16) & 2:
            return socket.inet_ntoa(struct.pack('<I', int(fields[2], 16)))
    raise ValueError('Container bridge gateway is unavailable; no peer trust was inferred.')


def create_app():
    if sys.platform != 'linux' or not Path('/.dockerenv').is_file():
        raise ValueError('Use backend.main for native execution.')
    peers = tuple(
        dict.fromkeys(
            [
                bridge_gateway(),
                *filter(None, os.environ.get('ATELIER_CONTAINER_PEERS', '').split(',')),
            ]
        )
    )
    data = Path(os.environ.get('ATELIER_DATA', '/data')).absolute()
    if not data.is_relative_to('/data') or '..' in data.parts:
        raise ValueError('Container DATA must stay inside the mounted /data volume.')
    from backend.main import create_app as platform_app

    return platform_app(
        data_root=data,
        deployment_profile=Profile('container', peers),
        initial_engine_url=os.environ.get('ATELIER_ENGINE_URL', 'http://host.docker.internal:8188'),
    )
