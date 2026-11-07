"""Regression checks for the actual committed presentation artifacts."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
ADVISOR = ROOT / "presentations/advisor"


class PresentationTests(unittest.TestCase):
    def test_dated_talk_is_checked_alongside_current_deck(self):
        from scripts.check_presentations import check
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / 'advisor'
            shutil.copytree(ADVISOR, directory, ignore=shutil.ignore_patterns('~$*', '__pycache__'))
            def update_manifest():
                files = sorted(p for p in directory.rglob('*')
                               if p.is_file() and p.name != 'SHA256SUMS')
                (directory / 'SHA256SUMS').write_text(''.join(
                    f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(directory).as_posix()}\n'
                    for p in files), encoding='utf-8')
            update_manifest()
            self.assertEqual(check(directory), [])
            talk = directory / 'research-talk-15min-2026-10-11.pptx'
            talk.write_bytes(b'truncated')
            update_manifest()
            self.assertTrue(any('PPTX ' + talk.name in e for e in check(directory)))

    def test_checker_rejects_truncated_deck_even_with_matching_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / 'advisor'
            shutil.copytree(ADVISOR, directory, ignore=shutil.ignore_patterns('~$*'))
            path = directory / 'advisor-presentation.pptx'
            path.write_bytes(path.read_bytes()[:700000])
            manifest = directory / 'SHA256SUMS'
            lines = []
            for line in manifest.read_text(encoding='utf-8').splitlines():
                digest, name = line.split(maxsplit=1)
                if name == path.name:
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
                lines.append(f'{digest}  {name}')
            manifest.write_text('\n'.join(lines)+'\n', encoding='utf-8')
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/check_presentations.py'),
                                     '--directory', str(directory)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('PPTX advisor-presentation.pptx', result.stderr)

    def test_current_content_has_complete_timing_and_closing_order(self):
        content = json.loads((ADVISOR / 'source/content.json').read_text(encoding='utf-8'))
        self.assertEqual(len(content['slides']), 16)
        self.assertEqual(content['main_slide_count'], 14)
        self.assertEqual(sum(s['seconds'] for s in content['slides']), 1080)
        self.assertEqual(content['slides'][13]['type'], 'closing')
        self.assertEqual(content['slides'][11]['title'], 'Три самостоятельных исследования')
        self.assertEqual(content['slides'][12]['title'], 'Общий стенд и границы личного вклада')

    def test_current_deck_has_portable_notes(self):
        with zipfile.ZipFile(ADVISOR / 'advisor-presentation.pptx') as archive:
            notes = b'\n'.join(archive.read(n) for n in archive.namelist()
                               if n.startswith('ppt/notesSlides/notesSlide') and n.endswith('.xml')).decode()
            self.assertNotIn('/Users/', notes)
            self.assertNotIn('/workspace/', notes)
            self.assertIn('docs/gitmark/research.md', notes)

    def test_current_objective_keeps_native_math_and_quality_constraint(self):
        ns = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
              'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
              'm': 'http://schemas.openxmlformats.org/officeDocument/2006/math'}
        with zipfile.ZipFile(ADVISOR / 'advisor-presentation.pptx') as archive:
            objective = ElementTree.fromstring(archive.read('ppt/slides/slide6.xml'))
            self.assertEqual(len(objective.findall('.//m:oMath', ns)), 6)
            self.assertEqual(len(objective.findall('.//m:limLow', ns)), 1)
            expected = {'5': 'minπ ∈ Π  𝔼Cagent(π, X)',
                        '7': '𝔼L(π, X) ≤ 𝔼L(π0, X) + ε'}
            for shape in objective.findall('.//p:sp', ns):
                shape_id = shape.find('p:nvSpPr/p:cNvPr', ns).get('id')
                if shape_id in expected:
                    math = shape.find('.//m:oMath', ns)
                    self.assertEqual(''.join(t.text or '' for t in math.findall('.//m:t', ns)),
                                     expected.pop(shape_id))
            self.assertFalse(expected, 'Primary equation shapes are missing')
            visible_text = ''.join(t.text or '' for t in objective.findall('.//a:t', ns))
            self.assertNotIn('C_agent', visible_text)
            self.assertNotIn('E[', visible_text)

    def test_cost_of_success_keeps_all_attempts_and_zero_success_guard(self):
        ns = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
              'm': 'http://schemas.openxmlformats.org/officeDocument/2006/math'}
        with zipfile.ZipFile(ADVISOR / 'advisor-presentation.pptx') as archive:
            cost = ElementTree.fromstring(archive.read('ppt/slides/slide10.xml'))
            self.assertEqual(len(cost.findall('.//m:f', ns)), 1)
            self.assertEqual(len(cost.findall('.//m:nary', ns)), 1)
            math = cost.find('.//m:oMath', ns)
            self.assertEqual(''.join(t.text or '' for t in math.findall('.//m:t', ns)),
                             'Csuccess = i = 1NCagent, iS')
            self.assertEqual(''.join(math.find('m:f/m:den', ns).itertext()), 'S')
            guard = ''.join(t.text or '' for t in cost.findall('.//a:t', ns))
            self.assertIn('S > 0', guard)
            self.assertIn('Все попытки входят в сумму.', guard)
            self.assertIn('При S = 0 стоимость успеха не определена', guard)

    def test_manifest_matches_actual_files(self):
        for line in (ADVISOR / "SHA256SUMS").read_text(encoding='utf-8').splitlines():
            digest, name = line.split(maxsplit=1)
            with self.subTest(file=name):
                self.assertEqual(hashlib.sha256((ADVISOR / name).read_bytes()).hexdigest(), digest)

