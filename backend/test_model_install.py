import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from scripts import install_pony as installer


class ModelInstallTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        self.content = b"safe checkpoint fixture, not a real model"
        self.manifest = copy.deepcopy(installer.load_manifest())
        self.manifest["size_bytes"] = len(self.content)
        self.manifest["sha256"] = hashlib.sha256(self.content).hexdigest()
        self.directory = self.workspace / "runtime" / "ComfyUI" / "models" / "checkpoints"
        self.directory.mkdir(parents=True)
        self.target = self.directory / self.manifest["filename"]
        self.partial = self.target.with_name(self.target.name + ".part")
        self.space = patch.object(installer.shutil, "disk_usage", return_value=type("Space", (), {"free": 100 * 1024**3})())
        self.space.start()
        self.addCleanup(self.space.stop)
        self.addCleanup(self.temporary.cleanup)

    def run_install(self, handler, **options):
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            return installer.install(workspace=self.workspace, manifest=self.manifest,
                                     client=client, output=lambda _: None, sleep=lambda _: None,
                                     **options)

    def no_network(self, _):
        self.fail("Unexpected network request")

    def response(self, status, body, headers=None):
        return httpx.Response(status, stream=httpx.ByteStream(body),
                              headers={"Content-Length": str(len(body))} | (headers or {}))

    def test_stream_download_verifies_and_publishes_with_provenance(self):
        result = self.run_install(lambda _: self.response(200, self.content))
        self.assertEqual(self.target.read_bytes(), self.content)
        self.assertFalse(self.partial.exists())
        self.assertTrue(result["verified"])
        self.assertFalse(result["reused"])
        self.assertEqual(result["source"]["revision"], self.manifest["source"]["revision"])
        provenance = json.loads(self.target.with_name(self.target.name + ".provenance.json").read_text(encoding="utf-8"))
        self.assertEqual(provenance["sha256"], self.manifest["sha256"])
        self.assertFalse(provenance["license"]["terms_verified"])
        self.assertFalse(list(self.directory.glob("*.install.lock")))

    def test_verified_existing_target_reuses_without_network(self):
        self.target.write_bytes(self.content)
        result = self.run_install(self.no_network)
        self.assertTrue(result["reused"])

    def test_different_existing_target_never_overwritten(self):
        wrong = b"x" * len(self.content)
        self.target.write_bytes(wrong)
        with self.assertRaisesRegex(installer.InstallationError, "拒絕覆蓋"):
            self.run_install(self.no_network, restart=True)
        self.assertEqual(self.target.read_bytes(), wrong)

    def test_resume_206_requires_exact_range_then_verifies_whole_file(self):
        offset = 8
        self.partial.write_bytes(self.content[:offset])
        def remote(request):
            self.assertEqual(request.headers["range"], f"bytes={offset}-")
            self.assertEqual(request.headers["accept-encoding"], "identity")
            return self.response(206, self.content[offset:], headers={
                "Content-Range": f"bytes {offset}-{len(self.content)-1}/{len(self.content)}"})
        self.run_install(remote)
        self.assertEqual(self.target.read_bytes(), self.content)

    def test_ignored_range_200_restarts_instead_of_appending(self):
        self.partial.write_bytes(b"old partial")
        def remote(request):
            self.assertEqual(request.headers["range"], "bytes=11-")
            return self.response(200, self.content)
        self.run_install(remote)
        self.assertEqual(self.target.read_bytes(), self.content)

    def test_mismatched_and_missing_content_range_do_not_append(self):
        before = self.content[:7]
        for content_range in (None, f"bytes 0-{len(self.content)-1}/{len(self.content)}",
                              f"bytes 7-{len(self.content)-1}/{len(self.content)+1}"):
            with self.subTest(content_range=content_range):
                self.partial.write_bytes(before)
                headers = {"Content-Range": content_range} if content_range else {}
                with self.assertRaisesRegex(installer.InstallationError, "Content-Range"):
                    self.run_install(lambda _: self.response(206, self.content[7:], headers=headers))
                self.assertEqual(self.partial.read_bytes(), before)
                self.assertFalse(self.target.exists())

    def test_complete_corrupt_partial_is_not_promoted_and_restart_can_repair(self):
        self.partial.write_bytes(b"x" * len(self.content))
        with self.assertRaisesRegex(installer.InstallationError, "SHA-256"):
            self.run_install(self.no_network)
        self.assertFalse(self.target.exists())
        self.assertTrue(self.partial.exists())
        self.run_install(lambda _: self.response(200, self.content), restart=True)
        self.assertEqual(self.target.read_bytes(), self.content)

    def test_corrupt_saved_prefix_fails_full_hash_after_valid_resume(self):
        self.partial.write_bytes(b"x" * 7)
        with self.assertRaisesRegex(installer.InstallationError, "SHA-256"):
            self.run_install(lambda _: self.response(206, self.content[7:], headers={
                "Content-Range": f"bytes 7-{len(self.content)-1}/{len(self.content)}"}))
        self.assertFalse(self.target.exists())
        self.assertEqual(self.partial.stat().st_size, len(self.content))

    def test_200_range_fallback_reclaims_partial_space_without_extra_copy(self):
        offset = 7
        self.partial.write_bytes(self.content[:offset])
        available = installer.RESERVE_BYTES + len(self.content) - offset
        with patch.object(installer.shutil, "disk_usage", return_value=type("Space", (), {"free": available})()):
            self.run_install(lambda _: self.response(200, self.content))
        self.assertEqual(self.target.read_bytes(), self.content)

    def test_disk_guard_accounts_for_only_remaining_bytes_plus_reserve(self):
        offset = 7
        self.partial.write_bytes(self.content[:offset])
        available = installer.RESERVE_BYTES + len(self.content) - offset - 1
        with patch.object(installer.shutil, "disk_usage", return_value=type("Space", (), {"free": available})()):
            with self.assertRaisesRegex(installer.InstallationError, "空間不足"):
                self.run_install(self.no_network)
        self.assertEqual(self.partial.read_bytes(), self.content[:offset])

    def test_disconnect_retry_resumes_saved_bytes_with_bounded_attempts(self):
        calls = []
        class BrokenStream(httpx.SyncByteStream):
            def __iter__(stream):
                yield self.content[:8]
                raise httpx.ReadError("Disconnected")
        def remote(request):
            calls.append(request)
            if len(calls) == 1:
                return httpx.Response(200, stream=BrokenStream())
            # Small chunks ensure the prefix has been written before failure.
            self.assertEqual(request.headers["range"], "bytes=8-")
            return self.response(206, self.content[8:], headers={
                "Content-Range": f"bytes 8-{len(self.content)-1}/{len(self.content)}"})
        with patch.object(installer, "CHUNK_BYTES", 4):
            self.run_install(remote)
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.target.read_bytes(), self.content)

    def test_transport_failure_has_finite_retries_and_cleans_lock(self):
        calls = []
        def remote(_):
            calls.append(True)
            raise httpx.ConnectError("Unavailable")
        with self.assertRaisesRegex(installer.InstallationError, "3 次"):
            self.run_install(remote)
        self.assertEqual(len(calls), 3)
        self.assertFalse(list(self.directory.glob("*.install.lock")))

    def test_nonretryable_http_error_does_not_repeat(self):
        calls = []
        def remote(_):
            calls.append(True)
            return httpx.Response(403)
        with self.assertRaisesRegex(installer.InstallationError, "HTTP 403"):
            self.run_install(remote)
        self.assertEqual(len(calls), 1)

    def test_range_body_cannot_exceed_or_disagree_with_header(self):
        self.partial.write_bytes(self.content[:7])
        before = self.partial.read_bytes()
        with self.assertRaisesRegex(installer.InstallationError, "Content-Length"):
            self.run_install(lambda _: self.response(206, self.content[7:] + b"excess", headers={
                "Content-Range": f"bytes 7-{len(self.content)-1}/{len(self.content)}"}))
        self.assertEqual(self.partial.read_bytes(), before)

    def test_filename_and_concurrent_install_lock_are_rejected(self):
        wrong = self.manifest | {"filename": "../../outside.safetensors"}
        with self.assertRaises(installer.InstallationError):
            installer.install(workspace=self.workspace, manifest=wrong)
        lock = self.target.with_name(self.target.name + ".install.lock")
        lock.write_text("fixture")
        with self.assertRaisesRegex(installer.InstallationError, "安裝鎖"):
            self.run_install(self.no_network)
        self.assertEqual(lock.read_text(), "fixture")

    def test_programmatic_manifest_also_requires_valid_pinned_source_and_digest(self):
        for change in ({"size_bytes": True}, {"sha256": "unknown"}, {"id": "other"},
                       {"source": self.manifest["source"] | {"download_url": "https://example.com/file"}}):
            with self.subTest(change=change), self.assertRaises(installer.InstallationError):
                installer.install(workspace=self.workspace, manifest=self.manifest | change)
        self.assertFalse(self.target.exists())
        self.assertFalse(list(self.directory.glob("*.install.lock")))

    def test_symlinked_runtime_outside_workspace_is_rejected_when_supported(self):
        with tempfile.TemporaryDirectory() as outside, tempfile.TemporaryDirectory() as fresh:
            runtime = Path(fresh) / "runtime"
            try:
                runtime.symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("Creating symlinks requires permissions on this host")
            with self.assertRaisesRegex(installer.InstallationError, "workspace/runtime 外"):
                installer.install(workspace=Path(fresh), manifest=self.manifest)
            self.assertFalse(list(Path(outside).iterdir()))


if __name__ == "__main__":
    unittest.main()
