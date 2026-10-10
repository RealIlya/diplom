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
    def test_checker_rejects_truncated_deck_even_with_matching_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / 'advisor'
            shutil.copytree(ADVISOR, directory)
            path = directory / 'advisor-presentation-v3-team.pptx'
            path.write_bytes(path.read_bytes()[:700000])
            manifest = directory / 'SHA256SUMS'
            lines = []
            for line in manifest.read_text().splitlines():
                digest, name = line.split(maxsplit=1)
                if name == path.name:
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
                lines.append(f'{digest}  {name}')
            manifest.write_text('\n'.join(lines)+'\n')
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/check_presentations.py'),
                                     '--directory', str(directory)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('PPTX advisor-presentation-v3-team.pptx', result.stderr)

    def test_current_content_has_complete_timing_and_closing_order(self):
        content = json.loads((ADVISOR / 'source/content-v4.json').read_text())
        self.assertEqual(len(content['slides']), 16)
        self.assertEqual(content['main_slide_count'], 14)
        self.assertEqual(sum(s['seconds'] for s in content['slides']), 1080)
        self.assertEqual(content['slides'][13]['type'], 'closing')
        self.assertEqual(content['slides'][11]['title'], 'Три самостоятельных исследования')
        self.assertEqual(content['slides'][12]['title'], 'Общий стенд и границы личного вклада')

    def test_current_deck_has_portable_notes(self):
        with zipfile.ZipFile(ADVISOR / 'advisor-presentation-v4-reviewed.pptx') as archive:
            notes = b'\n'.join(archive.read(n) for n in archive.namelist()
                               if n.startswith('ppt/notesSlides/notesSlide') and n.endswith('.xml')).decode()
            self.assertNotIn('/Users/', notes)
            self.assertNotIn('/workspace/', notes)
            self.assertIn('docs/research.md', notes)

    def test_all_stored_presentations_are_complete_packages(self):
        for path in ADVISOR.glob("*.pptx"):
            with self.subTest(file=path.name):
                with zipfile.ZipFile(path) as archive:
                    self.assertIsNone(archive.testzip())
                    ElementTree.fromstring(archive.read("ppt/presentation.xml"))

    def test_manifest_matches_actual_files(self):
        for line in (ADVISOR / "SHA256SUMS").read_text().splitlines():
            digest, name = line.split(maxsplit=1)
            with self.subTest(file=name):
                self.assertEqual(hashlib.sha256((ADVISOR / name).read_bytes()).hexdigest(), digest)

