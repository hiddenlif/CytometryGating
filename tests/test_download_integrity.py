import hashlib
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("fetch_public_data", Path(__file__).parents[1] / "scripts/fetch_public_data.py")
fetcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetcher)


def row_for(payload):
    return {
        "dataset": "fixture", "filename": "example.fcs", "path": "data/raw/fixture/example.fcs",
        "url": "https://example.invalid/example.fcs", "bytes": len(payload),
        "checksum_algorithm": "sha256", "checksum": hashlib.sha256(payload).hexdigest(),
    }


def test_existing_corrupt_file_is_not_accepted_or_overwritten(tmp_path, monkeypatch):
    monkeypatch.setattr(fetcher, "ROOT", tmp_path)
    dest = tmp_path / "data/raw/fixture/example.fcs"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"bad data")
    with pytest.raises(ValueError, match="Existing file failed"):
        fetcher.fetch(row_for(b"gooddata"))
    assert dest.read_bytes() == b"bad data"


def test_destination_cannot_escape_raw_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(fetcher, "ROOT", tmp_path)
    row = row_for(b"data")
    row["path"] = "data/raw/../../../escape.fcs"
    with pytest.raises(ValueError, match="escapes"):
        fetcher.fetch(row)


@pytest.mark.parametrize("payload,accepted", [(b"expected", True), (b"tampered", False)])
def test_download_checksum_controls_publication(tmp_path, monkeypatch, payload, accepted):
    monkeypatch.setattr(fetcher, "ROOT", tmp_path)

    class Response:
        def raise_for_status(self):
            pass

        def iter_content(self, size):
            yield payload

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def mount(self, *args):
            pass

        def get(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(fetcher.requests, "Session", Session)
    row = row_for(b"expected")
    dest = tmp_path / row["path"]
    if accepted:
        fetcher.fetch(row)
        assert dest.read_bytes() == payload
    else:
        with pytest.raises(ValueError, match="Checksum mismatch"):
            fetcher.fetch(row)
        assert not dest.exists()
    assert not dest.with_name(dest.name + ".part").exists()
