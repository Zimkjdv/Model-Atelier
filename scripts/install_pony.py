"""Shared pinned-weight downloader, with Pony as the legacy CLI default.

Run from the repository: python -m scripts.install_pony
Only fixed repository runtime/ComfyUI/models checkpoint, LoRA or ControlNet paths are used.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from typing import Callable

import httpx


WORKSPACE = Path(__file__).resolve().parents[1]
MANIFEST = WORKSPACE / "models" / "pony-v6-xl.json"
SOURCES = {
    'controlnet-canny-sdxl-1.0-fp16': ('diffusers/controlnet-canny-sdxl-1.0', 'diffusion_pytorch_model.fp16.safetensors', 'controlnet-canny-sdxl-1.0-fp16.safetensors', 'eb115a19a10d14909256db740ed109532ab1483c'),
    'pony-v6-xl': ('AstraliteHeart/pony-diffusion-v6', 'v6.safetensors', 'pony-v6-xl.safetensors', '5ec9c05863255568f1b59753e3838107befaa712'),
    'animagine-xl-4.0-opt': ('cagliostrolab/animagine-xl-4.0', 'animagine-xl-4.0-opt.safetensors', 'animagine-xl-4.0-opt.safetensors', '2b7c1b397761bf5bd3cc42e5b39ec99314a75a96'),
    'lcm-lora-sdxl': ('latent-consistency/lcm-lora-sdxl', 'pytorch_lora_weights.safetensors', 'lcm_lora_sdxl.safetensors', 'a18548dd4956b174ec5b0d78d340c8dae0a129cd'),
    'ikea-instructions-lora-sdxl': ('ostris/ikea-instructions-lora-sdxl', 'ikea_instructions_xl_v1_5.safetensors', 'ikea_instructions_xl_v1_5.safetensors', 'eaa7f67c93be0b22f00c0225d1f31232d91a052a'),
}
CONTROL_IDS = frozenset({'controlnet-canny-sdxl-1.0-fp16'})
LORA_IDS = frozenset({'lcm-lora-sdxl', 'ikea-instructions-lora-sdxl'})
RESERVE_BYTES = 2 * 1024**3
CHUNK_BYTES = 1024 * 1024


class InstallationError(RuntimeError):
    """A failed precondition, download or checkpoint verification."""


def load_manifest(path: Path = MANIFEST) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    return validate_manifest(value)


def validate_manifest(value: dict) -> dict:
    if not isinstance(value, dict):
        raise InstallationError("manifest 必須是 JSON object。")
    if not isinstance(value.get('id'), str) or value['id'] not in SOURCES:
        raise InstallationError("不支援的模型 manifest 或檔名。")
    repository, remote_filename, filename, pinned = SOURCES[value['id']]
    if value.get('filename') != filename:
        raise InstallationError('不支援的模型 manifest 或檔名。')
    if type(value.get("size_bytes")) is not int or value["size_bytes"] <= 0:
        raise InstallationError("manifest 檔案大小無效。")
    if not isinstance(value.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", value["sha256"]):
        raise InstallationError("manifest SHA-256 無效。")
    source = value.get("source", {})
    if not isinstance(source, dict):
        raise InstallationError("manifest source 必須是 object。")
    revision = source.get("revision", "")
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise InstallationError("來源必須固定至完整 commit。")
    expected = f"https://huggingface.co/{repository}/resolve/{pinned}/{remote_filename}"
    if (revision != pinned or source.get('repository') != repository or source.get('filename') != remote_filename
            or source.get("download_url") != expected):
        raise InstallationError("manifest 來源不是固定的作者 Hugging Face 檔案。")
    if any(not isinstance(value.get(key), str) or not value[key] for key in ("name", "version", "architecture")):
        raise InstallationError("manifest 名稱、版本或架構無效。")
    if not isinstance(value.get("license"), dict):
        raise InstallationError("manifest 缺少來源授權資訊。")
    return value


def _paths(workspace: Path, filename: str, *, create=True) -> tuple[Path, Path, Path, Path]:
    root = workspace.resolve()
    category = 'controlnet' if filename in {SOURCES[key][2] for key in CONTROL_IDS} else 'loras' if filename in {SOURCES[key][2] for key in LORA_IDS} else 'checkpoints'
    directory = (root / "runtime" / "ComfyUI" / "models" / category).resolve()
    if not directory.is_relative_to(root / "runtime"):
        raise InstallationError("模型目錄解析至 workspace/runtime 外，拒絕寫入。")
    if create:
        directory.mkdir(parents=True, exist_ok=True)
    target = directory / filename
    partial = directory / (filename + ".part")
    provenance = directory / (filename + ".provenance.json")
    lock = directory / (filename + ".install.lock")
    for path in (target, partial, provenance, lock):
        if path.is_symlink() or not path.resolve().is_relative_to(root / "runtime"):
            raise InstallationError("模型檔案不得是 symlink 或解析至 workspace/runtime 外。")
    return target, partial, provenance, lock


def _space(directory: Path, remaining: int) -> None:
    required = max(remaining, 0) + RESERVE_BYTES
    free = shutil.disk_usage(directory).free
    if free < required:
        raise InstallationError(
            f"可用磁碟空間不足：需要 {required / 1024**3:.2f} GiB "
            f"（含 2 GiB 預留），目前 {free / 1024**3:.2f} GiB。"
        )


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _verified(path: Path, manifest: dict) -> bool:
    return path.stat().st_size == manifest["size_bytes"] and _hash(path) == manifest["sha256"]


def _provenance(path: Path, manifest: dict, target: Path, reused: bool) -> dict:
    value = {
        "model_id": manifest["id"], "name": manifest["name"],
        "version": manifest["version"], "architecture": manifest["architecture"],
        "source": manifest["source"], "license": manifest["license"],
        "filename": target.name, "size_bytes": manifest["size_bytes"],
        "sha256": manifest["sha256"], "verified": True, "reused": reused,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }
    temporary = path.with_name(path.name + ".tmp")
    if temporary.is_symlink():
        raise InstallationError("provenance 暫存檔不得是 symlink。")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return value


def _promote(partial: Path, target: Path) -> None:
    # Windows rename refuses to replace an existing destination. On other systems,
    # a hard link provides the same atomic visibility with exclusive creation.
    if os.name == "nt":
        os.rename(partial, target)
    else:
        os.link(partial, target)
        partial.unlink()


def install(
    *, workspace: Path = WORKSPACE, manifest: dict | None = None,
    client: httpx.Client | None = None, restart: bool = False,
    attempts: int = 3, output: Callable[[str], None] = print,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict:
    manifest = load_manifest() if manifest is None else validate_manifest(manifest)
    if not 1 <= attempts <= 5:
        raise InstallationError("重試次數必須介於 1 與 5。")
    target, partial, provenance, lock = _paths(workspace, manifest["filename"])
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise InstallationError("同一模型已有安裝鎖；請確認其他安裝已停止，再移除該 .install.lock。") from exc
    owned_client = client is None
    try:
        with os.fdopen(descriptor, "w", encoding="ascii") as handle:
            handle.write(str(os.getpid()))
        if target.exists():
            output("已有 checkpoint，正在核對完整 SHA-256…")
            if not target.is_file() or not _verified(target, manifest):
                raise InstallationError("現有正式模型大小或 SHA-256 不符，拒絕覆蓋。請自行選擇其他檔名或移走該檔。")
            output("checkpoint 已驗證，沿用現有檔案。")
            return _provenance(provenance, manifest, target, True)
        if partial.exists() and not partial.is_file():
            raise InstallationError("partial 不是一般檔案。")
        if restart and partial.exists():
            partial.write_bytes(b"")
        size = manifest["size_bytes"]
        offset = partial.stat().st_size if partial.exists() else 0
        if offset > size:
            raise InstallationError("partial 大於預期模型，使用 --restart 明確重新下載。")
        _space(target.parent, size - offset)
        if client is None:
            client = httpx.Client(follow_redirects=True, trust_env=False,
                                  timeout=httpx.Timeout(60.0, connect=20.0))
        last_report = monotonic()
        output(f"下載 {manifest['name']}：{offset / 1024**2:.1f} / {size / 1024**2:.1f} MiB")
        for attempt in range(1, attempts + 1):
            offset = partial.stat().st_size if partial.exists() else 0
            if offset == size:
                break
            _space(target.parent, size - offset)
            headers = {"Accept-Encoding": "identity"}
            if offset:
                headers["Range"] = f"bytes={offset}-"
            try:
                with client.stream("GET", manifest["source"]["download_url"], headers=headers) as response:
                    if response.status_code not in (200, 206):
                        response.raise_for_status()
                        raise InstallationError(f"來源回傳不支援的 HTTP {response.status_code}。")
                    if response.headers.get("content-encoding", "identity").lower() != "identity":
                        raise InstallationError("來源使用非 identity 編碼，拒絕不可靠的 Range 續傳。")
                    if response.status_code == 206:
                        match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", response.headers.get("content-range", ""))
                        if not match:
                            raise InstallationError("206 缺少有效 Content-Range，拒絕 append。")
                        start, end, total = map(int, match.groups())
                        if start != offset or total != size or not start <= end < size:
                            raise InstallationError("Content-Range 與 partial/manifest 不符，拒絕 append。")
                        limit = end + 1
                        mode = "ab"
                    else:
                        # A server may ignore Range. Account for space reclaimed
                        # from this partial before discarding its saved prefix.
                        _space(target.parent, size - offset)
                        offset, limit, mode = 0, size, "wb"
                    expected_length = limit - offset
                    if "content-length" in response.headers:
                        try:
                            declared_length = int(response.headers["content-length"])
                        except ValueError as exc:
                            raise InstallationError("Content-Length 無效。") from exc
                        if declared_length != expected_length:
                            raise InstallationError("Content-Length 與預期範圍不符。")
                    received = 0
                    with partial.open(mode) as handle:
                        for chunk in response.iter_raw(chunk_size=CHUNK_BYTES):
                            if received + len(chunk) > expected_length:
                                raise InstallationError("來源資料超過宣告範圍，拒絕寫入額外資料。")
                            handle.write(chunk)
                            received += len(chunk)
                            current = monotonic()
                            if current - last_report >= 5:
                                output(f"下載進度：{(offset + received) / 1024**2:.1f} / {size / 1024**2:.1f} MiB")
                                last_report = current
                        handle.flush()
                        os.fsync(handle.fileno())
                    if received != expected_length:
                        raise httpx.ReadError("來源傳輸提前結束。")
                if partial.stat().st_size == size:
                    break
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in (408, 429, 500, 502, 503, 504):
                    raise InstallationError(f"下載失敗：HTTP {exc.response.status_code}。") from exc
                if attempt == attempts:
                    raise InstallationError(f"下載在 {attempts} 次嘗試後失敗；已保留 partial，可重新執行續傳。") from exc
                output(f"連線中斷，保留 partial；{attempt + 1}/{attempts} 次嘗試。")
                sleep(min(2**(attempt - 1), 4))
        if not partial.exists() or partial.stat().st_size != size:
            raise InstallationError("下載未達完整大小；已保留 partial，可重新執行續傳。")
        output("下載完成，正在核對完整 SHA-256…")
        if _hash(partial) != manifest["sha256"]:
            raise InstallationError("SHA-256 不符，未發布為正式 checkpoint；保留 partial，使用 --restart 明確重新下載。")
        try:
            _promote(partial, target)
        except FileExistsError as exc:
            raise InstallationError("目標正式模型在下載期間出現，拒絕覆蓋；已保留驗證完成的 partial。") from exc
        result = _provenance(provenance, manifest, target, False)
        output(f"安裝並驗證完成：{target}")
        return result
    finally:
        if owned_client and client is not None:
            client.close()
        lock.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restart", action="store_true", help="清空本模型的 partial，明確重新下載；不覆蓋正式模型")
    parser.add_argument("--attempts", type=int, default=3, help="本次最多連線嘗試次數（1–5）")
    args = parser.parse_args()
    try:
        install(restart=args.restart, attempts=args.attempts)
    except (InstallationError, OSError, ValueError) as exc:
        print(f"安裝失敗：{exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("安裝中止；保留 partial，下次執行可續傳。", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
