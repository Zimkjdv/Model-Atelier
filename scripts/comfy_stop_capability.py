"""Advertise targeted cancellation only for the audited ComfyUI source.

Read-only, standard library only. A version label or route existence does not
prove atomic interrupt semantics. Unknown/modified sources remain unsupported.
"""
import hashlib
import json
from pathlib import Path

FEATURE = 'model_atelier_atomic_job_cancel_v1'
SOURCE_COMMIT = '15eb748b3ec5f8a0a2d470b7fb280e2d7579f916'
HASHES = {
    'server.py': '74573b10465505b88b618da86059878e3a56418f84c7dae4073c8824aee35a6c',
    'execution.py': 'e4058e4cc03e89753f41a62f51d4534933a35e243358aa6796a65a9fd0bdda28',
    'comfy_execution/jobs.py': 'cee1191aa6ed913fde8b0556db9afa4f95135bdd910956b8d4bf921a81452085',
}


def verify(engine_root):
    try:
        supported = all(hashlib.sha256((engine_root / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest() == digest
                        for name, digest in HASHES.items())
    except OSError:
        supported = False
    return dict(supported=supported, feature_flag=FEATURE + '=' + SOURCE_COMMIT if supported else None,
                audited_commit=SOURCE_COMMIT if supported else None)


if __name__ == '__main__':
    print(json.dumps(verify(Path(__file__).resolve().parents[1] / 'runtime' / 'ComfyUI')))
