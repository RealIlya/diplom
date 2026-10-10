"""Regression checks for planner counts, references, and CLI serialization."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / '.agents/skills/agent-designer/agent_planner.py'
SAMPLE = ROOT / '.agents/skills/agent-designer/assets/sample_system_requirements.json'
EXPECTED = ROOT / '.agents/skills/agent-designer/expected_outputs/sample_agent_architecture.json'
spec = importlib.util.spec_from_file_location('agent_planner', SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def requirements(team_size, description='parallel hierarchical sequential tasks'):
    data = json.loads(SAMPLE.read_text())
    data['team_size'] = team_size
    data['description'] = description
    return module.SystemRequirements(**data)


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.planner = module.AgentPlanner()

    def check_design(self, design, size):
        self.assertEqual(len(design.agents), size)
        names = [agent.name for agent in design.agents]
        self.assertEqual(len(names), len(set(names)))
        for agent in design.agents:
            self.assertTrue(set(agent.dependencies or []).issubset(names))
            self.assertNotIn(agent.name, agent.dependencies or [])
        for link in design.communication_topology:
            self.assertIn(link.from_agent, names)
            self.assertIn(link.to_agent, names)

    def test_supported_patterns_preserve_size_and_references(self):
        cases = {
            module.AgentArchitecturePattern.SINGLE_AGENT: [1],
            module.AgentArchitecturePattern.SUPERVISOR: [2, 8],
            module.AgentArchitecturePattern.SWARM: [3, 10, 20],
            module.AgentArchitecturePattern.HIERARCHICAL: [5, 10, 20],
            module.AgentArchitecturePattern.PIPELINE: [3, 10, 15],
        }
        for pattern, sizes in cases.items():
            for size in sizes:
                with self.subTest(pattern=pattern, size=size):
                    agents = self.planner.design_agents(requirements(size), pattern)
                    links = self.planner.design_communication_topology(agents, pattern)
                    self.check_design(module.ArchitectureDesign(pattern, agents, links, [], [], {}, {}), size)

    def test_selected_patterns_at_boundaries(self):
        for size in [1, 2, 10, 20]:
            with self.subTest(size=size):
                design, _, _ = self.planner.plan_system(requirements(size))
                self.check_design(design, size)
                bounds = self.planner.pattern_heuristics[design.pattern]['team_size_range']
                self.assertLessEqual(bounds[0], size)
                self.assertGreaterEqual(bounds[1], size)

    def test_unsupported_pattern_and_invalid_team_sizes_refuse(self):
        for size in [0, 21]:
            with self.subTest(size=size), self.assertRaisesRegex(ValueError, 'team_size'):
                self.planner.plan_system(requirements(size))
        with self.assertRaisesRegex(ValueError, 'support'):
            self.planner.design_agents(requirements(2), module.AgentArchitecturePattern.HIERARCHICAL)

    def test_json_and_yaml_cli_roundtrip_enum_values(self):
        with tempfile.TemporaryDirectory() as temp:
            prefix = Path(temp) / 'architecture'
            for format_name in ['both', 'yaml']:
                result = subprocess.run([sys.executable, str(SCRIPT), str(SAMPLE),
                                         '-o', str(prefix), '--format', format_name],
                                        text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(prefix.with_suffix('.yaml').exists())
                yaml_data = yaml.safe_load(prefix.with_suffix('.yaml').read_text())
                design = yaml_data['architecture_design']
                self.assertIn(design['pattern'], [pattern.value for pattern in module.AgentArchitecturePattern])
                self.assertEqual(len(design['agents']), 6)
                self.assertTrue(all(agent['archetype'] in [role.value for role in module.AgentRole]
                                    for agent in design['agents']))
                self.assertTrue(all(link['pattern'] in [pattern.value for pattern in module.CommunicationPattern]
                                    for link in design['communication_topology']))
                if format_name == 'both':
                    self.assertEqual(yaml_data, json.loads(prefix.with_suffix('.json').read_text()))
                prefix.with_suffix('.yaml').unlink()

    def test_sample_fixture_is_generated_by_current_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            prefix = Path(temp) / 'sample_agent_architecture'
            result = subprocess.run([sys.executable, str(SCRIPT), SAMPLE.name,
                                     '-o', str(prefix), '--format', 'json'],
                                    cwd=SAMPLE.parent, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(prefix.with_suffix('.json').read_text()),
                             json.loads(EXPECTED.read_text()))


if __name__ == '__main__':
    unittest.main()
