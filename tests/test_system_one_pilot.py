"""Scientific boundaries of the offline pilot, without network or model weights."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from system_one_pilot.data import (build_split, snapshot, project, parse_kb,
                                   validate_rows, bm25, digest)
from system_one_pilot.model import binary_metrics, rank_metrics, admit, attach_annotations
from system_one_pilot.fetch import verify_file


def kb(doc_id="a", content="cash back applies"):
    return f"1. Rewards\n   ID: {doc_id}\n   Score: 1.0000\n   Content: {content}\n\n\n[Timing: retrieval=1ms, total=1ms]"


class PilotTests(unittest.TestCase):
    def test_download_integrity_is_checked_before_use(self):
        import tempfile
        import hashlib
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "data"
            path.write_bytes(b"pinned content")
            verify_file(path, hashlib.sha256(b"pinned content").hexdigest())
            path.write_bytes(b"changed content")
            with self.assertRaisesRegex(ValueError, "checksum"):
                verify_file(path, hashlib.sha256(b"pinned content").hexdigest())

    def test_pending_annotation_never_becomes_negative_target(self):
        row = {"id": "r", "task_id": "t", "split": "train", "family": "f", "input": {"state": "s", "candidate": "evidence"}, "label": None}
        manifest = {"tasks": {"t": {"split": "train", "family": "f"}}}
        annotation = {"row_id": "r", "input_sha256": digest(row["input"]), "quote_span": [0, 8], "rationale": "reason", "label": None}
        with self.assertRaisesRegex(ValueError, "annotation label"):
            attach_annotations([row], [annotation], manifest)

    def test_incomplete_tool_batch_refuses_snapshot(self):
        messages = [{"role": "assistant", "tool_calls": [{"id": "a", "name": "KB_search"}, {"id": "b", "name": "business"}]},
                    {"role": "tool", "requestor": "assistant", "id": "a", "content": kb()}]
        with self.assertRaisesRegex(ValueError, "incomplete tool batch"):
            snapshot(messages, 2)

    def test_metrics_keep_failures_and_uncertain_outside_binary_loss(self):
        metrics = binary_metrics([0, 1], [.1, .8])
        self.assertAlmostEqual(metrics["brier"], .025)
        self.assertAlmostEqual(metrics["accuracy"], 1.)
        with self.assertRaises(ValueError):
            binary_metrics([0, 1], [.1, float("nan")])
        self.assertAlmostEqual(rank_metrics([1, 0, 1], [3, 2, 1], 2)["recall_at_k"], .5)

    def test_exact_boundary_admission_refuses_truncation(self):
        class Tokenizer:
            mask_token = "[MASK]"
            def encode(self, text, add_special_tokens=False):
                return list(range(len(text)))
        self.assertEqual(admit(Tokenizer(), "12345", 5), [0, 1, 2, 3, 4])
        with self.assertRaises(ValueError):
            admit(Tokenizer(), "123456", 5)

    def test_shared_tool_name_is_not_shared_entity(self):
        tasks = [{"id": f"t{i}", "user_scenario": {"instructions": f"case {i}"},
                  "evaluation_criteria": {"actions": [{"name": "log_verification", "arguments": {"user_id": str(i)}}]}}
                 for i in range(6)]
        self.assertEqual(build_split(tasks, [], 19)["groups"], 6)

    def test_family_and_entity_siblings_never_cross_split(self):
        tasks = [{"id": f"task_{i:03}", "user_scenario": {"instructions": f"scenario {i}"},
                  "evaluation_criteria": {"actions": [{"arguments": {"user_id": "same" if i < 3 else str(i)}}]}}
                 for i in range(1, 12)]
        split = build_split(tasks, [["task_003", "task_004"]], 19)
        self.assertEqual(split, build_split(tasks, [["task_003", "task_004"]], 19))
        self.assertEqual(split["tasks"]["task_001"]["split"], split["tasks"]["task_002"]["split"])
        self.assertEqual(split["tasks"]["task_003"]["split"], split["tasks"]["task_004"]["split"])
        self.assertEqual(set(x["split"] for x in split["tasks"].values()), {"train", "dev", "test"})

    def test_visibility_cutoff_versions_and_projection_preserve_raw(self):
        messages = [
            {"role": "user", "content": "Do not close my card"},
            {"role": "user", "content": "PRIVATE", "tool_calls": [{"id": "private"}]},
            {"role": "tool", "requestor": "user", "id": "private", "content": "HIDDEN"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "k1", "name": "KB_search"}, {"id": "b1", "name": "get_balance"}]},
            {"role": "tool", "requestor": "assistant", "id": "k1", "content": kb()},
            {"role": "tool", "requestor": "assistant", "id": "b1", "content": "BALANCE"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "k2", "name": "KB_search"}]},
            {"role": "tool", "requestor": "assistant", "id": "k2", "content": kb(content="changed content")},
            {"role": "user", "content": "FUTURE"},
        ]
        original = copy.deepcopy(messages)
        s = snapshot(messages, 8)
        encoded = json.dumps(s)
        for sentinel in ["PRIVATE", "HIDDEN", "FUTURE"]:
            self.assertNotIn(sentinel, encoded)
        self.assertEqual(len(s["pool"]), 2)
        self.assertEqual({x["source_event"] for x in s["pool"]}, {4, 7})
        projected = project(s, [s["pool"][0]["candidate_id"]])
        self.assertIn("BALANCE", json.dumps(projected))
        self.assertNotIn("changed content", json.dumps(projected))
        self.assertEqual(messages, original)
        self.assertEqual(project(s, None), s["history"])
        with self.assertRaises(ValueError):
            project(s, ["unknown"])

    def test_ambiguous_kb_refuses_and_empty_is_valid(self):
        self.assertEqual(parse_kb("No relevant documents found.\n\n[Timing: retrieval=0ms, total=0ms]"), [])
        with self.assertRaises(ValueError):
            parse_kb("malformed\n" + kb())

    def test_dataset_rejects_test_hidden_and_conflicting_labels(self):
        manifest = {"tasks": {"t": {"split": "train", "family": "f"}, "x": {"split": "test", "family": "g"}}}
        row = {"id": "r", "task_id": "t", "split": "train", "family": "f", "input": {"state": "state", "candidate": "quote"}, "label": "useful"}
        validate_rows([row], manifest)
        for patch in [{"task_id": "x"}, {"input": {"required_documents": "SECRET"}}, {"label": "maybe"}]:
            with self.assertRaises(ValueError):
                validate_rows([dict(row, **patch)], manifest)
        with self.assertRaises(ValueError):
            validate_rows([row, dict(row, label="irrelevant")], manifest)

    def test_bm25_is_deterministic_ranking_not_probability(self):
        scores = bm25("cash rewards", ["cash rewards cash", "pin locked"])
        self.assertGreater(scores[0], scores[1])
        self.assertEqual(scores, bm25("cash rewards", ["cash rewards cash", "pin locked"]))


if __name__ == "__main__":
    unittest.main()
