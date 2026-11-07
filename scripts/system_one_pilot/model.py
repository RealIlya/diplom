"""Strict input admission and a CE-only head adaptation of the pinned Laya model."""
import collections
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import random
import statistics
import sys
import time
import traceback

from .data import bm25, digest, validate_rows, write_json

QUESTION = {"type": "noul", "instructions": "Does the candidate evidence contain a rule, exception or fact applicable to the current user need in the observed conversation?"}


def input_text(row):
    return "Observed conversation:\n" + row["input"]["state"] + "\nCandidate evidence:\n" + row["input"]["candidate"]


def admit(tokenizer, text, room):
    ids = tokenizer.encode(text, add_special_tokens=False)
    if len(ids) > room:
        raise ValueError(f"input_overflow: {len(ids)} > {room}")
    return ids


def binary_metrics(labels, probabilities):
    if not labels or len(labels) != len(probabilities) or not all(math.isfinite(p) and 0 <= p <= 1 for p in probabilities):
        raise ValueError("invalid metric inputs")
    n = len(labels)
    return {"n": n, "brier": sum((p-y)**2 for p, y in zip(probabilities, labels))/n,
            "nll": -sum(y*math.log(max(1e-7, p))+(1-y)*math.log(max(1e-7, 1-p)) for y, p in zip(labels, probabilities))/n,
            "accuracy": sum((p >= .5) == y for p, y in zip(probabilities, labels))/n}


def rank_metrics(labels, scores, k=3):
    if not labels or len(labels) != len(scores) or not all(math.isfinite(s) for s in scores):
        raise ValueError("invalid ranking inputs")
    order = sorted(range(len(labels)), key=lambda i: (-scores[i], i))
    k = min(k, len(order))
    hits = sum(labels[i] for i in order[:k])
    relevant = sum(labels)
    return {"precision_at_k": hits/k, "recall_at_k": hits/relevant if relevant else None,
            "k": k, "positives": relevant}


def attach_annotations(rows, annotations, manifest):
    lookup = {r["id"]: r for r in rows}
    if len(lookup) != len(rows):
        raise ValueError("duplicate queue IDs")
    result = []
    seen = set()
    for annotation in annotations:
        rid = annotation["row_id"]
        if rid in seen or rid not in lookup:
            raise ValueError("duplicate/unknown annotation")
        seen.add(rid)
        row = lookup[rid]
        if annotation.get("label") not in {"useful", "irrelevant", "uncertain"}:
            raise ValueError("annotation label must be useful/irrelevant/uncertain")
        if annotation["input_sha256"] != digest(row["input"]):
            raise ValueError("annotation input changed")
        a, b = annotation["quote_span"]
        if not (0 <= a < b <= len(row["input"]["candidate"])) or not annotation["rationale"].strip():
            raise ValueError("invalid annotation evidence")
        result.append(dict(row, label=annotation["label"]))
    validate_rows(result, manifest)
    return result


def runtime(laya_source, checkpoint):
    sys.path.insert(0, str(laya_source.resolve()))
    import torch
    from laya.train import load_checkpoint
    import laya
    if not Path(laya.__file__).resolve().is_relative_to(laya_source.resolve()):
        raise ValueError("imported Laya differs from requested source")
    # load_checkpoint applies the pinned upstream tokenizer compatibility patch.
    model, tokenizer, cfg = load_checkpoint(str(checkpoint.resolve()))
    return torch, model, tokenizer, cfg


def audit(args):
    from .cli import filehash, now
    sys.path.insert(0, str(args.laya_source.resolve()))
    from laya.agent import _fix_tokenizer_config
    from laya.train import to_internal
    from laya.common import state_room
    from transformers import AutoTokenizer
    _fix_tokenizer_config(str(args.checkpoint))
    tok = AutoTokenizer.from_pretrained(str(args.checkpoint / "tokenizer"), local_files_only=True)
    cfg = json.loads((args.checkpoint / "rl_agent_config.json").read_text())
    q = to_internal("useful", QUESTION)
    room = state_room(tok, q, cfg["max_len"], cfg["head_max_len"])
    counts, records = collections.Counter(), []
    for row in (json.loads(s) for s in args.queue.read_text().splitlines()):
        n = len(tok.encode(input_text(row), add_special_tokens=False))
        status = "accepted" if n <= room else "input_overflow"
        counts[row["split"] + "/" + status] += 1
        records.append({"row_id": row["id"], "task_id": row["task_id"], "split": row["split"],
                        "tokens": n, "room": room, "status": status})
    write_json(args.out, {"created_at": now(), "queue_sha256": filehash(args.queue),
                          "checkpoint": str(args.checkpoint), "max_len": cfg["max_len"],
                          "question": QUESTION, "counts": dict(counts), "rows": records})
    print(json.dumps(dict(counts)))


def fit(args):
    from .cli import CONFIG, filehash, now
    args.out.mkdir(parents=True, exist_ok=False)
    events = (args.out / "events.jsonl").open("x", buffering=1)
    started = time.monotonic()
    def emit(event, **kwargs):
        events.write(json.dumps({"time": now(), "event": event, **kwargs}, allow_nan=False) + "\n")
    summary = {"status": "running", "created_at": now(), "api_cost_usd": 0, "rental_cost_rub": 0,
               "local_energy_cost": None, "codex_session_cost": "not available in runtime",
               "test_used": False, "independent_human_label_review": False}
    try:
        config = json.loads(CONFIG.read_text())
        manifest = json.loads(args.split.read_text())
        if manifest["manifest_sha256"] != digest({k:v for k,v in manifest.items() if k != "manifest_sha256"}):
            raise ValueError("sealed split modified")
        if manifest["config_sha256"] != filehash(CONFIG):
            raise ValueError("config changed after sealed split")
        training = config["training"]
        if not (training["epochs"] == 1 and training["loss"] == "CE" and training["freeze_encoder"]
                and training["batch_size"] == 1 and not training["temperature_fit"]):
            raise ValueError("this pilot implements only one-epoch, batch-one, head-only CE without temperature fitting")
        if config["api_limit_usd"] != 0 or config["gpu_rental_limit_rub"] != 0:
            raise ValueError("this offline runner requires zero external spending")
        rows = [json.loads(s) for s in args.queue.read_text().splitlines()]
        queue_counts = dict(collections.Counter(r["split"] for r in rows))
        annotations = [json.loads(s) for s in args.annotations.read_text().splitlines()]
        rows = attach_annotations(rows, annotations, manifest)
        summary.update(config=config, split_sha256=manifest["manifest_sha256"],
                       queue_sha256=filehash(args.queue), annotations_sha256=filehash(args.annotations),
                       source_hashes={str(f): filehash(f) for f in Path(__file__).parent.glob("*.py")},
                       laya_source_root=str(args.laya_source.resolve()),
                       laya_source_sha256={str(f.relative_to(args.laya_source)): filehash(f) for f in (args.laya_source / "laya").rglob("*.py")},
                       cohort={"queue_by_split": queue_counts, "annotations": len(annotations),
                               "annotation_status": "provisional_machine_review", "evaluation_scope": "admitted, hard-labelled pairs only; not all native decisions"},
                       environment={"platform": platform.platform(), "python": sys.version,
                                    "packages": {p: importlib.metadata.version(p) for p in ["torch", "transformers", "tokenizers", "safetensors", "numpy", "huggingface_hub"]}},
                       checkpoint_hashes={str(f.relative_to(args.checkpoint)): filehash(f) for f in args.checkpoint.rglob("*") if f.is_file()})
        torch, model, tok, cfg = runtime(args.laya_source, args.checkpoint)
        checkpoint_manifest = json.loads(args.checkpoint_manifest.read_text())
        expected = next(c for c in checkpoint_manifest["checkpoints"] if c["repo"] == config["checkpoint_repo"] and c["revision"] == config["checkpoint_revision"])
        weights = next(f for f in expected["files"] if f["file"] == "model.safetensors")
        if filehash(args.checkpoint / "model.safetensors") != weights["upstream_lfs_sha256"]:
            raise ValueError("checkpoint differs from verified upstream weights")
        for entry in expected["files"]:
            if filehash(args.checkpoint / entry["file"]) != entry["sha256"]:
                raise ValueError("checkpoint config/tokenizer/weights differ from verified manifest")
        if cfg["max_len"] != training["max_len"] or cfg["head_max_len"] != training["head_max_len"]:
            raise ValueError("checkpoint input budget differs from protocol")
        from laya.train import to_internal, make_item, encode_item, _forward
        from laya.common import state_room, collate_items
        from safetensors.torch import save_file, load_file
        device = torch.device(args.device)
        if args.device == "mps" and not torch.backends.mps.is_available():
            raise RuntimeError("MPS unavailable; rerun outside sandbox or explicitly use --device cpu")
        torch.manual_seed(config["seed"])
        random.seed(config["seed"])
        model.to(device).eval()
        q = to_internal("useful", QUESTION)
        room = state_room(tok, q, cfg["max_len"], cfg["head_max_len"])
        items, admitted = {}, []
        admission_failures = []
        for row in rows:
            try:
                state_ids = admit(tok, input_text(row), room)
            except ValueError as exc:
                emit("admission_failure", row_id=row["id"], reason=str(exc))
                admission_failures.append({"row_id": row["id"], "reason": str(exc)})
                continue
            y = int(row["label"] == "useful")
            item, error = make_item(tok, q, [1-y, y], state_ids, cfg["head_max_len"], cfg["max_len"])
            if error:
                raise ValueError(error)
            items[row["id"]] = item
            admitted.append(row)
        train = [r for r in admitted if r["split"] == "train" and r["label"] != "uncertain"]
        dev = [r for r in admitted if r["split"] == "dev" and r["label"] != "uncertain"]
        if not train or not dev:
            raise ValueError("empty train or dev")
        summary.update(train_rows=len(train), dev_rows=len(dev), uncertain=sum(r["label"] == "uncertain" for r in admitted),
                       annotation_admission_failures=admission_failures,
                       train_families=len({r["family"] for r in train}), dev_families=len({r["family"] for r in dev}),
                       total_parameters=sum(p.numel() for p in model.parameters()), room=room, question=QUESTION)
        summary["training_recipe"] = {"epochs":1,"optimizer":"AdamW","head_lr":training["head_lr"],
                                      "weight_decay":.01,"gradient_clip":1.,"precision":"FP32","batch_size":1,
                                      "encoder":"frozen, eval mode","head":"train mode with dropout","calibration":"published, unchanged"}
        def sync():
            if device.type == "mps":
                torch.mps.synchronize()
        def forward(row):
            item = encode_item(tok, items[row["id"]], cfg["max_len"], cfg["head_max_len"])
            batch = collate_items([[item]], tok.pad_token_id)
            return _forward(model, batch, device, False, True)
        def evaluate(arm):
            model.eval()
            records = []
            for row in dev:
                sync(); start = time.monotonic()
                with torch.no_grad():
                    logits = forward(row)[0]
                    temperature = float(cfg.get("temperature_by_options", {}).get("noul:2", cfg["temperature"][2]))
                    probability = float(torch.softmax(logits/temperature, -1)[1].cpu())
                sync()
                if not math.isfinite(probability):
                    raise ValueError("nonfinite score")
                record = {"arm": arm, "row_id": row["id"], "task_id": row["task_id"],
                          "family": row["family"], "snapshot_id": row["snapshot_id"],
                          "input_sha256": digest(row["input"]), "label": int(row["label"] == "useful"),
                          "score": probability, "latency_seconds": time.monotonic()-start}
                records.append(record); emit("prediction", **record)
            return records
        frozen = evaluate("frozen")
        for name, parameter in model.named_parameters():
            parameter.requires_grad_(not name.startswith(("encoder.", "act_head.")))
        params = [p for p in model.parameters() if p.requires_grad]
        optimizer = torch.optim.AdamW(params, lr=config["training"]["head_lr"], weight_decay=.01)
        summary["trainable_parameters"] = sum(p.numel() for p in params)
        before = digest([float(p.detach().float().sum().cpu()) for p in params])
        model.train(); model.encoder.eval()
        order = list(train); random.Random(config["seed"]).shuffle(order)
        for step, row in enumerate(order[:config["training"]["max_steps"]]):
            if time.monotonic()-started > config["local_wall_limit_seconds"]:
                raise TimeoutError("local wall budget reached; partial events preserved")
            optimizer.zero_grad(set_to_none=True)
            logits = forward(row)
            loss = torch.nn.functional.cross_entropy(logits, torch.tensor([int(row["label"] == "useful")], device=device))
            if not torch.isfinite(loss):
                raise ValueError("nonfinite CE loss")
            loss.backward()
            grad = float(torch.nn.utils.clip_grad_norm_(params, 1.).cpu())
            if not math.isfinite(grad) or grad == 0:
                raise ValueError("nonfinite/zero gradient")
            optimizer.step(); sync()
            emit("train_step", step=step, row_id=row["id"], loss=float(loss.detach().cpu()), gradient_norm=grad)
            if step % 8 == 0:
                print(f"CE step {step+1}/{min(len(order), config['training']['max_steps'])}", flush=True)
        after = digest([float(p.detach().float().sum().cpu()) for p in params])
        if before == after:
            raise RuntimeError("parameters did not change")
        model.eval()
        adapted = evaluate("CE")
        head = {k: v.detach().cpu().contiguous() for k, v in model.state_dict().items() if not k.startswith("encoder.")}
        save_file(head, str(args.out / "adapted-head.safetensors"))
        # Verify reload onto the original model, not merely a second read of the same object.
        del optimizer, params, model
        if device.type == "mps":
            torch.mps.empty_cache()
        torch, model, tok, reloaded_cfg = runtime(args.laya_source, args.checkpoint)
        incompatible = model.load_state_dict(load_file(str(args.out / "adapted-head.safetensors")), strict=False)
        if incompatible.unexpected_keys or any(not k.startswith("encoder.") for k in incompatible.missing_keys):
            raise ValueError("invalid adapted head state")
        model.to(device).eval()
        reloaded = evaluate("CE_reloaded")
        difference = max(abs(a["score"]-b["score"]) for a,b in zip(adapted,reloaded))
        if difference > 1e-5:
            raise RuntimeError(f"save/reload changed scores: {difference}")
        groups = collections.defaultdict(list)
        for row in dev:
            groups[row["snapshot_id"]].append(row)
        lexical = []
        for group in groups.values():
            start=time.monotonic()
            scores=bm25(group[0]["input"]["state"], [r["input"]["candidate"] for r in group])
            elapsed=time.monotonic()-start
            for row, score in zip(group, scores):
                r={"arm":"BM25", "row_id":row["id"], "snapshot_id":row["snapshot_id"],
                   "score":score, "label":int(row["label"]=="useful"), "latency_seconds":elapsed/len(group)}
                lexical.append(r);emit("prediction",**r)
        result = {}
        for arm, records in [("BM25",lexical),("frozen",frozen),("CE",adapted)]:
            by_snapshot=collections.defaultdict(list)
            for record in records:by_snapshot[record["snapshot_id"]].append(record)
            rankings=[rank_metrics([r["label"] for r in group],[r["score"] for r in group]) for group in by_snapshot.values()]
            result[arm]={"n":len(records), "snapshots":len(rankings),
                         "mean_precision_at_3":statistics.mean(r["precision_at_k"] for r in rankings),
                         "mean_recall_at_3":statistics.mean(r["recall_at_k"] for r in rankings if r["recall_at_k"] is not None),
                         "latency_median_seconds":statistics.median(r["latency_seconds"] for r in records)}
            if arm!="BM25":result[arm].update(binary_metrics([r["label"] for r in records],[r["score"] for r in records]))
        summary.update(status="completed_diagnostic", results=result, reload_max_abs_difference=difference,
                       optimizer_steps=min(len(order),config["training"]["max_steps"]),
                       head_sha256=filehash(args.out/"adapted-head.safetensors"),
                       warning="Provisional single-agent labels and an admission-conditioned cohort; not evidence of generalization or agent success.")
        if device.type == "mps":
            summary["mps_current_allocated_bytes"]=torch.mps.current_allocated_memory()
            summary["mps_driver_allocated_bytes"]=torch.mps.driver_allocated_memory()
    except Exception as exc:
        summary.update(status="failed",error_type=type(exc).__name__,error=str(exc),traceback=traceback.format_exc())
        emit("failure", error_type=type(exc).__name__, reason=str(exc))
        raise
    finally:
        summary["elapsed_seconds"]=time.monotonic()-started
        write_json(args.out/"summary.json",summary)
        events.close()
        print(json.dumps({k:summary.get(k) for k in ["status","error","train_rows","dev_rows","results"]}),flush=True)
