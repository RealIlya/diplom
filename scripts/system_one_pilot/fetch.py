"""Acquire public pinned inputs; never call a paid inference service."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import urllib.request


def verify_file(path, expected):
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != expected:
        raise ValueError(f"checksum mismatch: {path}: {actual} != {expected}")


def acquire(manifest, out, verify_only=False):
    for entry in manifest["files"]:
        path = out / entry["path"]
        original = out / "checkpoint/tokenizer_config.original.json"
        checked = path
        if entry["path"] == "checkpoint/tokenizer/tokenizer_config.json" and original.exists():
            checked = original
        if checked.exists():
            verify_file(checked, entry["sha256"])
        elif verify_only:
            raise FileNotFoundError(checked)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            headers = {}
            if "range" in entry:
                a, b = entry["range"]
                headers["Range"] = f"bytes={a}-{b}"
            request = urllib.request.Request(entry["url"], headers=headers)
            # Interrupted downloads remain .part; never reuse unverified bytes.
            temporary = path.with_name(path.name + ".part")
            with urllib.request.urlopen(request, timeout=600) as response, temporary.open("xb") as stream:
                if "range" in entry and response.status != 206:
                    raise ValueError("server ignored pinned byte range")
                shutil.copyfileobj(response, stream)
            verify_file(temporary, entry["sha256"])
            temporary.rename(path)
        if entry["path"] == "checkpoint/tokenizer/tokenizer_config.json" and not original.exists():
            shutil.copyfile(path, original)
        if "extract_to" in entry and not verify_only:
            with tarfile.open(path) as archive:
                archive.extractall(out / entry["extract_to"], filter="data")
        print(entry["path"] + " verified", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("experiments/system-one-pilot/acquisition.json"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    acquire(json.loads(args.manifest.read_text()), args.out, args.verify_only)


if __name__ == "__main__":
    main()
