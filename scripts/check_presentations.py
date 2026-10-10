#!/usr/bin/env python3
"""Check saved presentation packages, the complete manifest and current notes."""
import argparse
import hashlib
import json
import posixpath
import sys
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET


def check(directory):
    errors = []
    manifest = {}
    for line in (directory / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or name in manifest:
            errors.append(f'Invalid or duplicate manifest path: {name}')
            continue
        manifest[name] = digest
        file = directory / name
        if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest() != digest:
            errors.append(f'SHA-256 mismatch/missing: {name}')
    files = {p.relative_to(directory).as_posix() for p in directory.rglob('*')
             if p.is_file() and p.name != 'SHA256SUMS' and '__pycache__' not in p.parts}
    if files != set(manifest):
        errors.append(f'Manifest coverage: missing={sorted(files-set(manifest))}; stale={sorted(set(manifest)-files)}')
    current = 'advisor-presentation-v4-reviewed.pptx'
    content = json.loads((directory / 'source/content-v4.json').read_text())
    if len(content['slides']) != 16 or content['main_slide_count'] != 14:
        errors.append('Current content must have 16 slides, 14 main')
    if sum(s['seconds'] for s in content['slides']) != 1080 or content['total_seconds'] != 1080:
        errors.append('Main talk timing must total 1080 seconds')
    for file in directory.glob('*.pptx'):
        try:
            with zipfile.ZipFile(file) as archive:
                if archive.testzip():
                    raise ValueError('ZIP CRC failure')
                names = set(archive.namelist())
                for name in names:
                    if name.endswith(('.xml', '.rels')):
                        xml = ET.fromstring(archive.read(name))
                        if name.endswith('.rels'):
                            base = posixpath.dirname(posixpath.dirname(name))
                            for rel in xml:
                                if rel.get('TargetMode') == 'External':
                                    continue
                                target = rel.attrib['Target'].split('#', 1)[0]
                                resolved = (target.lstrip('/') if target.startswith('/') else
                                            posixpath.normpath(posixpath.join(base, target)))
                                if resolved not in names:
                                    raise ValueError(f'Missing relationship target: {resolved}')
                presentation = ET.fromstring(archive.read('ppt/presentation.xml'))
                slides = presentation.find('{http://schemas.openxmlformats.org/presentationml/2006/main}sldIdLst')
                if file.name == current:
                    if len(slides) != len(content['slides']):
                        raise ValueError('Slide count differs from current content')
                    notes = [n for n in names if n.startswith('ppt/notesSlides/notesSlide') and n.endswith('.xml')]
                    text = '\n'.join(archive.read(n).decode() for n in notes)
                    if len(notes) != 16 or '/Users/' in text or '/workspace/' in text or 'docs/research.md' not in text:
                        raise ValueError('Current notes missing or contain nonportable paths')
        except (zipfile.BadZipFile, ET.ParseError, KeyError, ValueError, TypeError) as exc:
            errors.append(f'PPTX {file.name}: {exc}')
    if not (directory / current).is_file():
        errors.append(f'Missing current deck: {current}')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'presentations/advisor')
    args = parser.parse_args()
    try:
        errors = check(args.directory)
    except (OSError, ValueError, KeyError) as exc:
        errors = [str(exc)]
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print('Presentation ZIP/XML/relationships, current content/notes and complete SHA-256 manifest: PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
