"""Behavioral regressions for the imported tool schema generator."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / '.agents/skills/agent-designer/tool_schema_generator.py'
spec = importlib.util.spec_from_file_location('tool_schema_generator', SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def tool(inputs, examples=None):
    return module.ToolDescription(
        name='send', purpose='Send', category='communication', inputs=inputs,
        outputs=[], error_conditions=[], side_effects=[], idempotent=True,
        rate_limits={}, dependencies=[], examples=examples or [],
        security_requirements=[],
    )


class SchemaTests(unittest.TestCase):
    def setUp(self):
        self.generator = module.ToolSchemaGenerator()

    def test_nested_required_is_array_and_parent_required_stays_at_root(self):
        description = tool([{
            'name': 'payload', 'type': 'object', 'description': 'Payload',
            'required': True, 'properties': {'value': {'type': 'string'}},
            'required_properties': ['value'],
        }])
        generated = self.generator.generate_tool_schema(description)
        for schema in (generated.openai_schema['parameters'], generated.anthropic_schema['input_schema']):
            Draft202012Validator.check_schema(schema)
            self.assertEqual(schema['required'], ['payload'])
            self.assertEqual(schema['properties']['payload']['required'], ['value'])
            self.assertFalse(Draft202012Validator(schema).is_valid({'payload': {}}))

    def test_array_identifier_description_does_not_change_type_or_items(self):
        description = tool([{
            'name': 'recipients', 'type': 'array', 'description': 'List of recipient identifiers',
            'required': True, 'items': {'type': 'string', 'pattern': '^user_'},
            'min_items': 1,
        }], [{'input': {'recipients': ['user_one']}}])
        generated = self.generator.generate_tool_schema(description)
        for schema in (generated.openai_schema['parameters'], generated.anthropic_schema['input_schema']):
            Draft202012Validator.check_schema(schema)
            prop = schema['properties']['recipients']
            self.assertEqual(prop['type'], 'array')
            self.assertEqual(prop['items'], {'type': 'string', 'pattern': '^user_'})
            self.assertTrue(Draft202012Validator(schema).is_valid({'recipients': ['user_one']}))
            self.assertFalse(Draft202012Validator(schema).is_valid({'recipients': ['other']}))

    def test_explicit_format_preserves_declared_type_and_rules(self):
        description = tool([
            {'name': 'address', 'type': 'string', 'description': 'Delivery address', 'format': 'email'},
            {'name': 'ids', 'type': 'array', 'description': 'IDs', 'items': {'type': 'integer'}, 'format': 'uuid'},
        ])
        generated = self.generator.generate_tool_schema(description)
        for schema in (generated.openai_schema['parameters'], generated.anthropic_schema['input_schema']):
            Draft202012Validator.check_schema(schema)
            self.assertEqual(schema['properties']['address']['format'], 'email')
            self.assertEqual(schema['properties']['ids']['type'], 'array')
            self.assertEqual(schema['properties']['ids']['items'], {'type': 'integer'})
            self.assertNotIn('format', schema['properties']['ids'])

    def test_cli_validate_examples_and_empty_tool(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            no_params = tool([])
            bad = tool([{'name': 'count', 'type': 'integer', 'description': 'Count', 'required': True}],
                       [{'input': {'count': 'not an integer'}}])
            malformed = tool([{'name': 'payload', 'type': 'object', 'description': 'Payload',
                               'required_properties': {'wrong': 'shape'}}],
                             [{'input': {'payload': {}}}])
            for name, desc, expected_code in [('empty', no_params, 0), ('bad', bad, 1),
                                              ('malformed', malformed, 1)]:
                input_path = base / f'{name}.json'
                input_path.write_text(json.dumps({'tools': [desc.__dict__]}))
                result = subprocess.run([sys.executable, str(SCRIPT), str(input_path),
                                         '-o', str(base / name), '--format', 'json', '--validate'],
                                        text=True, capture_output=True)
                self.assertEqual(result.returncode, expected_code, result.stdout + result.stderr)
                if name == 'bad':
                    self.assertIn('example', result.stdout + result.stderr)
                if name == 'malformed':
                    self.assertIn('schema', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
