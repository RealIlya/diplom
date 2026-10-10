"""Fail when the committed MkDocs output differs from a strict fresh build."""

import argparse
import filecmp
import subprocess
import sys
import tempfile
from pathlib import Path


def compare_directories(fresh: Path, tracked: Path) -> list[str]:
    fresh_files = {p.relative_to(fresh).as_posix(): p for p in fresh.rglob("*") if p.is_file()}
    tracked_files = {p.relative_to(tracked).as_posix(): p for p in tracked.rglob("*") if p.is_file()}
    differences = [f"missing: {name}" for name in sorted(fresh_files.keys() - tracked_files.keys())]
    differences += [f"extra: {name}" for name in sorted(tracked_files.keys() - fresh_files.keys())]
    differences += [
        f"different: {name}"
        for name in sorted(fresh_files.keys() & tracked_files.keys())
        if not filecmp.cmp(fresh_files[name], tracked_files[name], shallow=False)
    ]
    return differences


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    repo = args.repo.resolve()
    with tempfile.TemporaryDirectory(prefix="diplom-site-") as temporary:
        fresh = Path(temporary) / "site"
        result = subprocess.run(
            [sys.executable, "-m", "mkdocs", "build", "--strict", "--site-dir", str(fresh)],
            cwd=repo,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            print(result.stdout + result.stderr, file=sys.stderr)
            return result.returncode
        differences = compare_directories(fresh, repo / "site")
    if differences:
        print("Tracked site differs from a fresh strict build:", file=sys.stderr)
        for difference in differences[:50]:
            print(f"  {difference}", file=sys.stderr)
        if len(differences) > 50:
            print(f"  ... and {len(differences) - 50} more", file=sys.stderr)
        return 1
    print("Tracked site matches the fresh strict MkDocs build.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
