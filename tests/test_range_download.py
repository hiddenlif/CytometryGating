import importlib.util
import io
import re
import zipfile
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("redox_archive", Path(__file__).parents[1] / "scripts/inspect_redox_archive.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Response:
    def __init__(self, body, status, content_range):
        self.raw = io.BytesIO(body)
        self.status_code = status
        self.headers = {"Content-Range": content_range}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def test_zipfile_can_seek_and_extract_through_bounded_ranges(monkeypatch):
    buffer = io.BytesIO()
    payload = b"Known archive member contents"
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        zipped.writestr("cohort/example.bin", payload)
    archive = buffer.getvalue()

    def get(url, headers, **kwargs):
        match = re.fullmatch(r"bytes=(\d+)-(\d+)", headers["Range"])
        start, end = map(int, match.groups())
        return Response(archive[start:end + 1], 206, f"bytes {start}-{end}/{len(archive)}")

    with module.RemoteZipReader("https://example.invalid/archive.zip", len(archive), budget=4096) as remote:
        monkeypatch.setattr(remote.session, "get", get)
        with zipfile.ZipFile(remote) as zipped:
            assert zipped.read("cohort/example.bin") == payload
        assert 0 < remote.used <= remote.budget


@pytest.mark.parametrize("status,content_range,body", [
    (200, "bytes 0-2/10", b"abc"),
    (206, "bytes 1-3/10", b"abc"),
    (206, "bytes 0-2/10", b"ab"),
    (206, "bytes 0-2/10", b"abcd"),
])
def test_invalid_partial_response_is_rejected_without_advancing(monkeypatch, status, content_range, body):
    with module.RemoteZipReader("https://example.invalid/archive.zip", 10) as remote:
        monkeypatch.setattr(remote.session, "get", lambda *args, **kwargs: Response(body, status, content_range))
        with pytest.raises(ValueError):
            remote.read(3)
        assert remote.tell() == 0
        assert remote.used == 0


def test_budget_refuses_download_before_network_access(monkeypatch):
    with module.RemoteZipReader("https://example.invalid/archive.zip", 100, budget=4) as remote:
        def unexpected_request(*args, **kwargs):
            pytest.fail("Budget failure must happen before network access")
        monkeypatch.setattr(remote.session, "get", unexpected_request)
        with pytest.raises(ValueError, match="budget"):
            remote.read(5)
