"""Split tasks before replay; expose only observations and preserve their lineage."""
import collections
import copy
import hashlib
import itertools
import json
import math
import re


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")


def entity_keys(value):
    result = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"user_id", "account_id", "card_id", "transaction_id", "customer_name", "name", "email", "phone_number"} and isinstance(item, str) and item.strip():
                result.add((key, item.casefold()))
            elif isinstance(item, (dict, list)):
                result |= entity_keys(item)
    elif isinstance(value, list):
        for item in value:
            result |= entity_keys(item)
    return result


def ngrams(text):
    words = re.findall(r"[a-z]+", text.lower())
    return set(zip(*(words[i:] for i in range(5))))


def build_split(tasks, manual_groups, seed):
    ids = [t["id"] for t in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate task ID")
    parent = dict(zip(ids, ids))
    edges = []

    def root(a):
        while parent[a] != a:
            a = parent[a]
        return a

    def join(a, b, reason):
        if a not in parent or b not in parent:
            raise ValueError("unknown manual task ID")
        parent[root(b)] = root(a)
        edges.append({"a": a, "b": b, "reason": reason})

    for group in manual_groups:
        for a, b in zip(group, group[1:]):
            join(a, b, "reviewed template/ancestry")
    features = {}
    for task in tasks:
        features[task["id"]] = (entity_keys([a.get("arguments", {}) for a in task.get("evaluation_criteria", {}).get("actions", [])]),
                                 ngrams(task["user_scenario"]["instructions"]))
    for a, b in itertools.combinations(ids, 2):
        ea, na = features[a]
        eb, nb = features[b]
        shared = ea & eb
        similarity = len(na & nb) / max(1, len(na | nb))
        if shared:
            join(a, b, "shared concrete reference entity")
        elif similarity >= 0.55:
            join(a, b, f"scenario 5-gram Jaccard {similarity:.4f} >= 0.55")
    groups = collections.defaultdict(list)
    for task_id in sorted(ids):
        groups[root(task_id)].append(task_id)
    ordered = sorted(groups.values(), key=lambda g: (-len(g), digest([seed, g])))
    target = {"train": len(ids) * .6, "dev": len(ids) * .2, "test": len(ids) * .2}
    counts = dict.fromkeys(target, 0)
    assignments = {}
    for group in ordered:
        # Largest-first bin packing, independent of observations and outcomes.
        split = max(target, key=lambda s: (target[s] - counts[s]) / target[s])
        counts[split] += len(group)
        family = "family-" + digest(group)[:12]
        for task_id in group:
            assignments[task_id] = {"split": split, "family": family}
    return {"version": 1, "seed": seed, "algorithm": "entity/template/5gram-components-largest-deficit",
            "counts": counts, "groups": len(groups), "tasks": assignments, "edges": edges,
            "task_hashes": {t["id"]: digest(t) for t in tasks}}


KB_HEADER = re.compile(r"(?m)^\d+\. ([^\n]+)\n   ID: ([^\n]+)\n   Score: ([0-9.eE+\-]+)\n   Content: ")
KB_TOOLS = {"KB_search", "KB_search_bm25", "KB_search_dense"}


def parse_kb(text):
    if text.startswith("No relevant documents found."):
        return []
    matches = list(KB_HEADER.finditer(text))
    if not matches or matches[0].start() != 0:
        raise ValueError("ambiguous KB formatter")
    result = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[match.end():end]
        if i + 1 == len(matches):
            body = re.sub(r"\n+\[Timing:[^\n]*\]\s*$", "", body)
        body = body.rstrip("\n")
        title, doc_id, score = match.groups()
        if not math.isfinite(float(score)):
            raise ValueError("nonfinite retrieval score")
        result.append({"document_id": doc_id, "title": title, "content": body,
                       "content_sha256": hashlib.sha256(body.encode()).hexdigest()})
    return result


def snapshot(messages, cutoff):
    if not 0 <= cutoff <= len(messages):
        raise ValueError("invalid cutoff")
    history, pool, calls, kb_events, pending = [], {}, {}, [], set()
    for event, source in enumerate(messages[:cutoff]):
        role = source.get("role")
        if role not in {"assistant", "user", "tool"}:
            continue
        if role == "user" and source.get("tool_calls"):
            continue
        if role == "tool" and source.get("requestor") != "assistant":
            continue
        # Explicit allowlist; no gold/reward/task fields copied from native trace.
        message = {k: copy.deepcopy(source[k]) for k in ("role", "content", "tool_calls", "id", "requestor", "name") if k in source}
        if role == "assistant":
            if pending:
                raise ValueError("incomplete tool batch before assistant")
            for call in message.get("tool_calls") or []:
                calls[call["id"]] = call["name"]
                pending.add(call["id"])
        if role == "tool":
            pending.discard(message.get("id"))
        if role == "tool" and calls.get(message.get("id")) in KB_TOOLS:
            for doc in parse_kb(message["content"]):
                key = doc["document_id"] + "@" + doc["content_sha256"]
                if key not in pool:
                    pool[key] = dict(doc, candidate_id=key, source_event=event, tool_call_id=message["id"])
            kb_events.append(len(history))
        history.append(message)
    if pending:
        raise ValueError("incomplete tool batch at cutoff")
    state_history = copy.deepcopy(history)
    for index in kb_events:
        state_history[index]["content"] = "[KB retrieval received; candidates scored separately]"
    result = {"cutoff": cutoff, "history": history, "kb_history_indices": kb_events,
              "state": json.dumps(state_history, ensure_ascii=False, separators=(",", ":")),
              "pool": list(pool.values())}
    result["snapshot_sha256"] = digest(result)
    return result


def project(snap, selected):
    if selected is None:
        return copy.deepcopy(snap["history"])
    lookup = {x["candidate_id"]: x for x in snap["pool"]}
    if len(set(selected)) != len(selected) or not set(selected) <= lookup.keys():
        raise ValueError("invalid candidate IDs")
    messages = copy.deepcopy(snap["history"])
    for index in snap["kb_history_indices"]:
        messages[index]["content"] = "[KB retrieval received; see selected evidence]"
    evidence = "\n\n".join(lookup[x]["content"] for x in selected)
    if selected:
        messages.append({"role": "user", "content": "Selected observed evidence:\n" + evidence})
    return messages


def validate_rows(rows, manifest):
    seen = set()
    inputs = {}
    for row in rows:
        task = manifest["tasks"].get(row["task_id"])
        if not task or task["split"] == "test" or row["split"] != task["split"] or row["family"] != task["family"]:
            raise ValueError("test/split/ancestry violation")
        if row["id"] in seen:
            raise ValueError("duplicate row ID")
        seen.add(row["id"])
        if set(row["input"]) != {"state", "candidate"} or not all(isinstance(v, str) for v in row["input"].values()):
            raise ValueError("input allowlist violation")
        if row.get("label") not in {None, "useful", "irrelevant", "uncertain"}:
            raise ValueError("invalid label")
        key = digest(row["input"])
        if key in inputs and inputs[key] != row["split"]:
            raise ValueError("cross-split duplicate input")
        inputs[key] = row["split"]


def bm25(query, documents):
    tokenize = lambda s: re.findall(r"[a-z0-9]+", s.casefold())
    tokens = [tokenize(x) for x in documents]
    average = sum(map(len, tokens)) / max(1, len(tokens))
    result = [0.0] * len(tokens)
    for term in set(tokenize(query)):
        df = sum(term in doc for doc in tokens)
        idf = math.log(1 + (len(tokens) - df + .5) / (df + .5))
        for i, doc in enumerate(tokens):
            freq = doc.count(term)
            if freq:
                result[i] += idf * freq * 2.5 / (freq + 1.5 * (.25 + .75 * len(doc) / max(1, average)))
    return result
