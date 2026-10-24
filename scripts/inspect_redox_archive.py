"""Inspect the public CAR-T CyTOF ZIP with bounded HTTP ranges; optionally fetch five pilot files.

ZIP member CRCs and local SHA256 are recorded. A partial archive download does
not verify the publisher's MD5 of the entire archive.
"""

import argparse
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

import flowkit as fk
import requests

ROOT = Path(__file__).resolve().parents[1]


class RemoteZipReader(io.RawIOBase):
    def __init__(self, url, size, budget=128 * 1024 * 1024):
        self.url, self.size, self.budget = url, size, budget
        self.pos = self.used = 0
        self.session = requests.Session()

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        if whence not in (0, 1, 2):
            raise ValueError("Invalid seek mode")
        position = (
            offset
            if whence == 0
            else self.pos + offset
            if whence == 1
            else self.size + offset
        )
        if position < 0:
            raise ValueError("Negative seek")
        self.pos = position
        return self.pos

    def read(self, count=-1):
        count = self.size - self.pos if count < 0 else min(count, self.size - self.pos)
        if count <= 0:
            return b""
        if count > 64 * 1024 * 1024 or self.used + count > self.budget:
            raise ValueError("Bounded range-read budget exceeded")
        start, end = self.pos, self.pos + count - 1
        with self.session.get(
            self.url,
            headers={"Range": f"bytes={start}-{end}"},
            timeout=(20, 60),
            stream=True,
        ) as response:
            if response.status_code != 206:
                raise ValueError(
                    f"Server did not honor bounded range: {response.status_code}"
                )
            expected = f"bytes {start}-{end}/{self.size}"
            if response.headers.get("Content-Range") != expected:
                raise ValueError("Unexpected Content-Range")
            # Bound actual body reads even if the server returns malformed headers.
            data = response.raw.read(count + 1)
        if len(data) != count:
            raise ValueError("Range length mismatch")
        self.pos += count
        self.used += count
        return data

    def close(self):
        self.session.close()
        super().close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fetch-pilot",
        action="store_true",
        help="Fetch the smallest FCS for each archive patient code",
    )
    args = parser.parse_args()
    source = json.loads((ROOT / "data/discovery/redox.source.json").read_text())
    archive = next(f for f in source["files"] if f["key"] == "CAR-T_CyTOF.zip")
    records, groups = [], {}
    with RemoteZipReader(archive["links"]["self"], archive["size"]) as remote:
        with zipfile.ZipFile(remote) as zipped:
            for info in zipped.infolist():
                if (
                    info.is_dir()
                    or info.filename.startswith("__MACOSX/")
                    or not info.filename.lower().endswith(".fcs")
                ):
                    continue
                match = re.search(r"_CART(\d+)_", info.filename)
                code = match.group(1) if match else None
                record = {
                    "member": info.filename,
                    "uncompressed_bytes": info.file_size,
                    "compressed_bytes": info.compress_size,
                    "crc32": f"{info.CRC:08x}",
                    "encrypted": bool(info.flag_bits & 1),
                    "patient_code_from_filename": code,
                }
                records.append(record)
                if code:
                    groups.setdefault(code, []).append((info, record))
            pilot = []
            if args.fetch_pilot:
                for code, entries in sorted(groups.items()):
                    info, record = min(entries, key=lambda x: x[0].compress_size)
                    data = zipped.read(info)  # zipfile verifies the member CRC.
                    sample = fk.Sample(io.BytesIO(data), preprocess=False)
                    dest = (
                        ROOT / "data/raw/redox-cytof-pilot" / Path(info.filename).name
                    )
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(data)
                    pilot.append(
                        {
                            "patient_code": code,
                            "member": info.filename,
                            "local_path": str(dest.relative_to(ROOT)),
                            "member_crc32_verified": True,
                            "sha256": hashlib.sha256(data).hexdigest(),
                            "events": sample.event_count,
                            "channels": sample.pnn_labels,
                            "marker_labels": sample.pns_labels,
                        }
                    )
        report = {
            "record": "https://zenodo.org/records/11541294",
            "archive_filename": archive["key"],
            "archive_publisher_checksum": archive["checksum"],
            "full_archive_checksum_verified": False,
            "download_mode": "HTTP byte ranges; ZIP member CRC verification for fetched pilot files",
            "network_bytes": remote.used,
            "real_fcs_members": len(records),
            "patient_codes_in_inventory": sorted(groups),
            "files_per_patient_code": {k: len(v) for k, v in sorted(groups.items())},
            "control_or_unmapped_files": sum(
                r["patient_code_from_filename"] is None for r in records
            ),
            "study_reported_patients": 7,
            "limitation": f"The inspected archive contains {len(groups)} filename patient codes; clinical-table reconciliation remains outstanding. Different modality: mass cytometry, post-infusion monitoring. Do not substitute the study-wide count, pool with fluorescence data, or claim raw/unprocessed acquisitions without processing review.",
            "files": records,
            "pilot": pilot,
        }
    out = ROOT / "reports/local/donor-discovery/redox-inspection.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in report.items() if k not in {"files", "pilot"}}, indent=2
        )
    )
    print("Pilot files parsed:", len(pilot))


if __name__ == "__main__":
    main()
