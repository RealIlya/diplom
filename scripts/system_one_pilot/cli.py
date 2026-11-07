"""Run with `python3 -m scripts.system_one_pilot.cli --help`. No paid API path."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import re
import sys
from datetime import datetime, timezone

from .data import build_split, digest, snapshot, validate_rows, write_json

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "experiments/system-one-pilot/config.json"


def filehash(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def prepare(args):
    cfg = json.loads(CONFIG.read_text())
    base = args.tau / "data/tau2/domains/banking_knowledge"
    tasks = [json.loads(f.read_text()) for f in sorted((base / "tasks").glob("task_*.json"))]
    if len(tasks) != 97:
        raise ValueError("expected pinned 97 tasks")
    manifest = build_split(tasks, cfg["manual_groups"], cfg["seed"])
    manifest.update(created_at=now(), config_sha256=filehash(CONFIG),
                    warning="Conservative automated + agent template audit; no independent human audit. Public tasks previously inspected in project; not pristine blind test.")
    manifest["manifest_sha256"] = digest(manifest)
    write_json(args.out / "split.json", manifest)
    files = sorted(f for f in base.rglob("*") if f.is_file())
    files += sorted(f for f in (args.tau / "src/tau2").rglob("*.py"))
    files += [args.tau / "LICENSE", args.tau / "pyproject.toml"]
    sources = {str(f.relative_to(args.tau)): filehash(f) for f in files}
    write_json(args.out / "source-manifest.json", {
        "created_at": now(), "tau_revision": cfg["tau_revision"],
        "files": sources, "documents": len(list((base / "documents").glob("*.json"))),
        "license": "MIT at repository root; archive trajectories have no separately verified license; local use only, raw bodies not redistributed",
        "source_root": str(args.tau.resolve()), "split_sha256": manifest["manifest_sha256"]})
    print(json.dumps({"counts": manifest["counts"], "families": manifest["groups"], "split_sha256": manifest["manifest_sha256"]}))


def read_archive_prefix(path, cfg):
    if path.stat().st_size != cfg["archive_prefix_bytes"] or filehash(path) != cfg["archive_sha256"]:
        raise ValueError("archive size/hash mismatch")
    text = path.read_bytes().decode("utf8", "ignore")
    decoder = json.JSONDecoder()
    start = re.search(r'^  "simulations": \[', text, re.M)
    if not start:
        raise ValueError("archive schema mismatch")
    position = start.end()
    simulations = []
    while True:
        position = re.compile(r"[\s,]*").match(text, position).end()
        try:
            item, position = decoder.raw_decode(text, position)
        except json.JSONDecodeError:
            break
        simulations.append(item)
    start_info = re.search(r'^  "info": ', text, re.M)
    info, _ = decoder.raw_decode(text, start_info.end())
    return simulations, info


def replay(args):
    cfg = json.loads(CONFIG.read_text())
    manifest = json.loads((args.manifests / "split.json").read_text())
    if manifest["config_sha256"] != filehash(CONFIG):
        raise ValueError("config changed after sealed split")
    simulations, info = read_archive_prefix(args.archive, cfg)
    seen, rows, snaps, errors = set(), [], [], []
    skipped = collections.Counter()
    for sim in simulations:
        task_id = sim["task_id"]
        task = manifest["tasks"].get(task_id)
        if not task:
            raise ValueError("unknown archive task")
        if task["split"] == "test":
            skipped["test_episode_not_extracted"] += 1
            continue
        if task_id in seen:
            skipped["repeated_task"] += 1
            continue
        seen.add(task_id)
        # Only complete native tool batches: snapshot just before the next assistant.
        for cutoff, message in enumerate(sim["messages"]):
            if message["role"] != "assistant":
                continue
            try:
                snap = snapshot(sim["messages"], cutoff)
            except ValueError as exc:
                errors.append({"task_id": task_id, "cutoff": cutoff, "error": str(exc)})
                break
            if not snap["pool"]:
                continue
            snap_id = digest([task_id, snap["snapshot_sha256"]])
            snap.update(id=snap_id, task_id=task_id, **task)
            snaps.append(snap)
            for doc in snap["pool"]:
                spans = list(re.finditer(r"\S+", doc["content"]))
                for chunk in range(0, len(spans), cfg["replay"]["chunk_words"]):
                    start = spans[chunk].start()
                    end = spans[min(len(spans), chunk + cfg["replay"]["chunk_words"]) - 1].end()
                    candidate = doc["content"][start:end]
                    row_id = digest([snap_id, doc["candidate_id"], start, end])[:20]
                    rows.append({"id": row_id, "task_id": task_id, **task,
                                 "snapshot_id": snap_id, "document_id": doc["document_id"],
                                 "source_event": doc["source_event"], "content_sha256": doc["content_sha256"],
                                 "char_span": [start, end], "title": doc["title"],
                                 "input": {"state": snap["state"], "candidate": "Title: " + doc["title"] + "\nFragment:\n" + candidate}, "label": None})
            break
    validate_rows(rows, manifest)
    args.out.mkdir(parents=True, exist_ok=False)
    for name, records in [("snapshots.jsonl", snaps), ("queue.jsonl", rows)]:
        with (args.out / name).open("x") as f:
            for row in records:
                f.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    report = {"created_at": now(), "split_sha256": manifest["manifest_sha256"],
              "archive_sha256": cfg["archive_sha256"], "complete_archive_episodes": len(simulations),
              "skipped": dict(skipped), "errors": errors, "source_info": info,
              "rows": len(rows), "snapshots": len(snaps),
              "tasks_by_split": {s: sorted({r["task_id"] for r in rows if r["split"] == s}) for s in ["train", "dev"]},
              "queue_sha256": filehash(args.out / "queue.jsonl"),
              "preprocessing_sha256": {str(f): filehash(f) for f in Path(__file__).parent.glob("*.py")},
              "new_api_cost_usd": 0, "original_archive_generation_cost": "unknown/excluded from marginal replay cost"}
    write_json(args.out / "replay-manifest.json", report)
    print(json.dumps({k: report[k] for k in ["rows", "snapshots", "tasks_by_split", "skipped", "errors"]}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare")
    p.add_argument("--tau", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(func=prepare)
    p = commands.add_parser("replay")
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--manifests", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(func=replay)
    from .model import audit, fit
    p = commands.add_parser("audit")
    p.add_argument("--queue", type=Path, required=True)
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--laya-source", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(func=audit)
    p = commands.add_parser("fit")
    p.add_argument("--queue", type=Path, required=True)
    p.add_argument("--annotations", type=Path, required=True)
    p.add_argument("--split", type=Path, required=True)
    p.add_argument("--checkpoint-manifest", type=Path, required=True)
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--laya-source", type=Path, required=True)
    p.add_argument("--device", choices=["cpu", "mps"], default="mps")
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(func=fit)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
