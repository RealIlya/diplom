"""Regression tests for the imported agent-designer evaluator (not the research harness)."""

from dataclasses import asdict, replace
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/agent-designer"
SPEC = importlib.util.spec_from_file_location("vendor_agent_evaluator", SKILL / "agent_evaluator.py")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def log(task_id, *, actions=None, tools_used=None, start="2024-01-01T00:00:00Z", end="2024-01-01T00:00:10Z"):
    return {
        "task_id": task_id,
        "agent_id": "worker",
        "task_type": "example",
        "status": "success",
        "start_time": start,
        "end_time": end,
        "duration_ms": 10000,
        "actions": actions or [],
        "tools_used": tools_used or [],
    }


class AgentEvaluatorTests(unittest.TestCase):
    def test_retry_count_does_not_invent_retry_latency(self):
        evaluator = MODULE.AgentEvaluator()
        raw = log('retry_without_duration', actions=[
            {'type': 'tool_call', 'tool_name': 'search', 'duration_ms': 7,
             'success': False, 'retry_count': 2},
        ], tools_used=['search'])
        logs = evaluator.parse_execution_logs([raw])
        report = evaluator.generate_report(logs)
        usage = report.tool_usage_analysis['search']
        self.assertEqual(usage['retry_count'], 2)
        self.assertEqual(usage['avg_duration'], 7)
        bottleneck = next(b for b in report.bottleneck_analysis if b.bottleneck_type == 'tool')
        self.assertNotIn('retry_overhead', bottleneck.impact_on_performance)

    def test_sample_cli_generates_complete_report(self):
        """The distributed sample must be consumable without a constructor error."""
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory) / "sample_report"
            completed = subprocess.run(
                [sys.executable, str(SKILL / "agent_evaluator.py"),
                 str(SKILL / "assets/sample_execution_logs.json"), "-o", str(prefix)],
                capture_output=True, text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(prefix.with_suffix(".json").read_text())
            metrics = report["system_metrics"]
            self.assertEqual(metrics["total_tasks"], 10)
            self.assertEqual(metrics["successful_tasks"], 6)
            self.assertEqual(metrics["success_rate"], 0.6)
            self.assertEqual(metrics["average_duration_ms"], 146700)
            self.assertEqual(metrics["total_tokens_used"], 44600)
            self.assertAlmostEqual(metrics["total_cost_usd"], 0.887)
            self.assertTrue({"summary", "system_metrics", "tool_usage_analysis", "optimization_recommendations"} <= report.keys())
            for suffix in ("_summary.json", "_recommendations.json", "_errors.json"):
                self.assertTrue(prefix.with_name(prefix.name + suffix).exists())

    def test_every_recommendation_branch_constructs_complete_record(self):
        evaluator = MODULE.AgentEvaluator()
        baseline = evaluator.calculate_performance_metrics(evaluator.parse_execution_logs([log("a"), log("b")]))
        metrics = replace(baseline, success_rate=0.5, average_cost_per_task=0.2,
                          average_duration_ms=40000, throughput_tasks_per_hour=2,
                          total_cost_usd=2)
        error = MODULE.ErrorAnalysis("timeout", 1, 50, ["worker"], ["example"],
                                     [], ["reduce timeout"], "high")
        bottleneck = MODULE.BottleneckAnalysis("agent", "worker", "critical", "slow",
                                               {"latency_impact": 100}, ["example"],
                                               ["reduce latency"], {"latency_reduction": 0.3})
        recommendations = evaluator.generate_optimization_recommendations(metrics, [error], [bottleneck])
        self.assertEqual(len(recommendations), 6)
        for recommendation in recommendations:
            record = asdict(recommendation)
            self.assertIn("estimated_cost_savings", record)
            self.assertIn("estimated_performance_gain", record)
            self.assertTrue(record["implementation_steps"])

    def test_tool_usage_uses_individual_action_outcomes_and_durations(self):
        raw = log("failed_task", actions=[
            {"type": "tool_call", "tool_name": "search", "duration_ms": 100, "success": True},
            {"type": "tool_call", "tool_name": "search", "duration_ms": 300, "success": False},
            {"type": "tool_call", "tool_name": "lookup", "duration_ms": 50, "success": True},
        ], tools_used=["search", "lookup"])
        raw["status"] = "failure"
        raw["error_details"] = {"message": "task failed after tool calls"}
        evaluator = MODULE.AgentEvaluator()
        result = evaluator._analyze_tool_usage(evaluator.parse_execution_logs([raw]))
        self.assertEqual(result["search"]["usage_count"], 2)
        self.assertEqual(result["search"]["avg_duration"], 200)
        self.assertEqual(result["search"]["error_rate"], 0.5)
        self.assertEqual(result["lookup"]["usage_count"], 1)
        self.assertEqual(result["lookup"]["avg_duration"], 50)
        self.assertEqual(result["lookup"]["error_rate"], 0)

    def test_missing_action_telemetry_is_unknown_and_not_a_tool_failure(self):
        raw = log("unobserved", tools_used=["search"])
        another = log("partial_action", actions=[{"type": "tool_call", "tool_name": "lookup"}])
        evaluator = MODULE.AgentEvaluator()
        logs = evaluator.parse_execution_logs([raw, another])
        usage = evaluator._analyze_tool_usage(logs)
        self.assertEqual(usage["search"]["usage_count"], 0)
        self.assertEqual(usage["search"]["unobserved_task_count"], 1)
        self.assertIsNone(usage["search"]["avg_duration"])
        self.assertIsNone(usage["search"]["error_rate"])
        self.assertIsNone(usage["search"]["retry_count"])
        self.assertEqual(usage["lookup"]["usage_count"], 1)
        self.assertIsNone(usage["lookup"]["avg_duration"])
        self.assertIsNone(usage["lookup"]["error_rate"])
        self.assertIsNone(usage["lookup"]["retry_count"])
        bottlenecks = evaluator.identify_bottlenecks(logs, {
            "worker": evaluator.calculate_performance_metrics(logs)
        })
        self.assertFalse(any(b.bottleneck_type == "tool" for b in bottlenecks))

    def test_missing_time_telemetry_does_not_imply_low_throughput(self):
        raw = [log("a", start="", end=""), log("b", start="", end="")]
        evaluator = MODULE.AgentEvaluator()
        report = evaluator.generate_report(evaluator.parse_execution_logs(raw))
        self.assertIsNone(report.system_metrics.throughput_tasks_per_hour)
        self.assertIsNone(report.summary["evaluation_period"]["total_duration_hours"])
        self.assertFalse(any(rec.category == "scalability" for rec in report.optimization_recommendations))

    def test_incomplete_tool_outcomes_do_not_trigger_error_bottleneck(self):
        evaluator = MODULE.AgentEvaluator()
        raw = [log("observed", actions=[
            {"type": "tool_call", "tool_name": "search", "success": False, "duration_ms": 100}
        ], tools_used=["search"]), log("unobserved", tools_used=["search"])]
        logs = evaluator.parse_execution_logs(raw)
        usage = evaluator._analyze_tool_usage(logs)["search"]
        self.assertEqual(usage["error_rate"], 1.0)
        self.assertEqual(usage["unobserved_task_count"], 1)
        bottlenecks = evaluator.identify_bottlenecks(logs, {
            "worker": evaluator.calculate_performance_metrics(logs)
        })
        self.assertFalse(any(b.bottleneck_type == "tool" for b in bottlenecks))


if __name__ == "__main__":
    unittest.main()
