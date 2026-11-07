"""Measure visible tau banking history with KEV's tokenizer; no model inference.

Requires the already-installed tokenizers package and curl. Fetches only a
pinned 20 MB public trajectory prefix and a 12.8 MB tokenizer into memory.
This is a nonrandom prefix sample, NOT a benchmark-wide fit-rate estimate.
Run: python3 scripts/measure_tau_history_context.py
"""
import collections
import concurrent.futures
import hashlib
import json
import re
import subprocess

from tokenizers import Tokenizer

ARTIFACT = (
    "https://sierra-tau-bench-public.s3.us-west-2.amazonaws.com/submissions/"
    "gpt-5-4_sierra_2026-03-25/trajectories/"
    "gpt-5.4_xhigh_banking_knowledge_gpt-5.2_4trials.json"
)
TOKENIZER = (
    "https://huggingface.co/Qwen/Qwen3.5-4B-Base/resolve/"
    "1001bb4d826a52d1f399e183466143f4da7b741b/tokenizer.json"
)
SAMPLE_SHA256 = "4d7f30616a6c158079d1569e8213fbad20518d7725284af197d1383459ebe993"
TOKENIZER_SHA256 = "fe000e3ed39ed12b8d2481d527d44f93c65d37e87645d2dcc80d1bf9d50d2927"


def fetch(url, byte_range=None):
    args = ["curl", "-fsSL", "--max-time", "60", "--max-filesize", "20000000"]
    if byte_range:
        args += ["-r", byte_range]
    return subprocess.check_output(args + [url])


def compact_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def stats(values):
    ordered = sorted(values)

    def quantile(frac):
        pos = (len(ordered) - 1) * frac
        low = int(pos)
        high = min(low + 1, len(ordered) - 1)
        return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)

    count_over = sum(value > 8192 for value in ordered)
    return dict(
        n=len(ordered), min=min(ordered), p50=quantile(0.5), p90=quantile(0.9),
        max=max(ordered), n_gt8192=count_over, frac_gt8192=count_over / len(ordered),
    )


def main():
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        artifact_future = pool.submit(fetch, ARTIFACT, "0-19999999")
        tokenizer_future = pool.submit(fetch, TOKENIZER)
        raw, tokraw = artifact_future.result(), tokenizer_future.result()
    assert len(raw) == 20_000_000
    assert hashlib.sha256(raw).hexdigest() == SAMPLE_SHA256
    assert hashlib.sha256(tokraw).hexdigest() == TOKENIZER_SHA256
    tokenizer = Tokenizer.from_str(tokraw.decode())
    tokenizer.no_truncation()
    tokenizer.no_padding()

    def token_count(text):
        return len(tokenizer.encode(text, add_special_tokens=False).ids)

    # The range can split the final UTF-8 codepoint; only complete objects count.
    text = raw.decode("utf8", "ignore")
    decoder = json.JSONDecoder()
    start = re.search(r'^  "simulations": \[', text, re.M)
    assert start is not None
    position = start.end()
    simulations = []
    while True:
        position = re.compile(r"[\s,]*").match(text, position).end()
        try:
            simulation, position = decoder.raw_decode(text, position)
        except json.JSONDecodeError:
            break  # Discard the incomplete final simulation, never count a prefix as a run.
        simulations.append(simulation)
    assert len(simulations) == 52
    info_start = re.search(r'^  "info": ', text, re.M)
    assert info_start is not None
    info, _ = decoder.raw_decode(text, info_start.end())

    all_prefixes, rollout_maxima, content_only, max_tool = [], [], [], []
    retained, excluded = collections.Counter(), collections.Counter()
    for simulation in simulations:
        history, prefixes, tool_lengths = [], [], []
        last_text = ""
        for message in simulation["messages"]:
            role = message["role"]
            if role == "user" and message.get("tool_calls"):
                excluded["user_tool_call"] += 1
                continue
            if role == "tool" and message.get("requestor") != "assistant":
                excluded["user_tool_result"] += 1
                continue
            if role not in ("assistant", "user", "tool"):
                continue
            if role == "assistant" and history:
                prefixes.append(token_count(compact_json(history)))
                last_text = "\n".join(item.get("content") or "" for item in history)
            item = {"role": role, "content": message.get("content")}
            if role == "assistant" and message.get("tool_calls"):
                item["tool_calls"] = [
                    {"id": call["id"], "type": "function", "function": {
                        "name": call["name"],
                        "arguments": call["arguments"] if isinstance(call["arguments"], str)
                        else compact_json(call["arguments"]),
                    }} for call in message["tool_calls"]
                ]
            if role == "tool":
                item["tool_call_id"] = message["id"]
                tool_lengths.append(token_count(message["content"]))
            history.append(item)
            retained[role] += 1
        all_prefixes.extend(prefixes)
        rollout_maxima.append(max(prefixes))
        content_only.append(token_count(last_text))
        max_tool.append(max(tool_lengths))
    assert len(all_prefixes) == 703
    result = {
        "artifact": ARTIFACT, "sample_range": "bytes=0-19999999",
        "sample_sha256": SAMPLE_SHA256, "tokenizer": TOKENIZER,
        "tokenizer_sha256": TOKENIZER_SHA256,
        "artifact_revision": info["git_commit"],
        "unique_tasks": len({item["task_id"] for item in simulations}),
        "rollouts": len(simulations), "retained": dict(retained), "excluded": dict(excluded),
        "history_only_predecision": stats(all_prefixes),
        "per_rollout_max_predecision": stats(rollout_maxima),
        "last_predecision_content_only": stats(content_only),
        "largest_single_tool_result_per_rollout": stats(max_tool),
        "policy_tokens": token_count(info["environment_info"]["policy"]),
        "tool_defs_present": info["environment_info"]["tool_defs"] is not None,
        "limitations": "Nonrandom file-prefix sample. No policy/tools/question in history counts. "
        "Not a native chat template, KEV inference or benchmark-wide estimate.",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
