"""Check that vendored documentation and fixtures remain usable with its CLIs."""

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / ".agents/skills/agent-designer"


class VendorExamplesTests(unittest.TestCase):
    def test_readme_json_examples_run_with_cli(self):
        readme = (VENDOR / "README.md").read_text()
        requirements, tools, _logs = (json.loads(block) for block in re.findall(r"```json\n(.*?)\n```", readme, re.S))
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for label, data, script, validate in (
                ("requirements", requirements, "agent_planner.py", []),
                ("tools", tools, "tool_schema_generator.py", ["--validate"]),
            ):
                input_file = directory / f"{label}.json"
                input_file.write_text(json.dumps(data))
                output = directory / f"{label}_output"
                command = [sys.executable, str(VENDOR / script), str(input_file), "-o", str(output), *validate]
                result = subprocess.run(command, cwd=directory, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, f"{command}: {result.stdout} {result.stderr}")
                self.assertTrue(output.with_suffix(".json").exists())

    def test_schema_fixture_has_all_sample_tools(self):
        sample = json.loads((VENDOR / "assets/sample_tool_descriptions.json").read_text())
        fixture = json.loads((VENDOR / "expected_outputs/sample_tool_schemas.json").read_text())
        self.assertEqual([schema["name"] for schema in fixture["tool_schemas"]],
                         [tool["name"] for tool in sample["tools"]])
        self.assertEqual(fixture["metadata"]["tool_count"], len(sample["tools"]))

    def test_upstream_license_notice_is_preserved(self):
        content = (VENDOR / "LICENSE").read_bytes()
        blob = b"blob " + str(len(content)).encode() + b"\0" + content
        self.assertEqual(hashlib.sha1(blob).hexdigest(), "9d84f9e269c910c4ba7e636f6c3febce1c468ac4")


if __name__ == "__main__":
    unittest.main()
