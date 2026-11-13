"""Inventory packaged modules and fail closed on project test modules."""
import argparse
import base64
import gzip
import hashlib
import io
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

REPO = Path(__file__).resolve().parents[1]
OWN_TESTS = {p.stem for p in (REPO / 'tests').glob('test_*.py')}
OWN_SCRIPTS = {p.stem for p in (REPO / 'scripts').glob('*.py')}


def forbidden(name):
    name = name.replace('\\', '/').replace('/', '.')
    parts = name.split('.')
    return (any(p in OWN_TESTS or p in OWN_SCRIPTS for p in parts)
            or name == 'tests' or name.startswith('tests.'))


def inventory_pyinstaller(path):
    from PyInstaller.archive.readers import CArchiveReader
    archive = CArchiveReader(str(path))
    packaged = sorted(archive.toc)
    pyzs = [name for name in archive.toc if name.lower().endswith('.pyz')]
    if len(pyzs) != 1:
        raise ValueError('Expected exactly one PYZ archive')
    modules = sorted(archive.open_embedded_archive(pyzs[0]).toc)
    base = []
    if 'base_library.zip' in archive.toc:
        with zipfile.ZipFile(io.BytesIO(archive.extract('base_library.zip'))) as z:
            base = sorted(z.namelist())
    return {'format': 'pyinstaller', 'modules': modules, 'archive_entries': packaged, 'base_library': base}


def inventory_nuitka(path):
    root = ET.parse(path).getroot()
    if root.tag != 'nuitka-compilation-report' or root.get('completion') != 'yes':
        raise ValueError('Incomplete or invalid Nuitka compilation report')
    modules = sorted(node.get('name') for node in root.findall('module') if node.get('name'))
    files = sorted(node.get('name') for tag in ('data_file', 'data_blob')
                   for node in root.findall(tag) if node.get('name'))
    origins = [node.get(attr, '') for tag, attr in (('module', 'source_path'), ('data_file', 'source'))
               for node in root.findall(tag)]
    prefixes = ('${cwd}/tests/', '${cwd}/scripts/',
                (REPO / 'tests').as_posix() + '/', (REPO / 'scripts').as_posix() + '/')
    project_sources = sorted(path for path in origins
                             if any(path.replace('\\', '/').casefold().startswith(prefix.casefold()) for prefix in prefixes))
    return {'format': 'nuitka', 'modules': modules, 'data_files': files,
            'project_test_or_tool_sources': project_sources}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('format', choices=['pyinstaller', 'nuitka'])
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = inventory_pyinstaller(args.input) if args.format == 'pyinstaller' else inventory_nuitka(args.input)
    names = result['modules'] + result.get('archive_entries', []) + result.get('base_library', []) + result.get('data_files', [])
    if not any(name.startswith('controller.') for name in result['modules']) or not any(name.startswith('ofxtools') for name in result['modules']):
        raise ValueError('Inventory did not contain expected application and OFX modules')
    bad = sorted(set(name for name in names if forbidden(name)) | set(result.get('project_test_or_tool_sources', [])))
    result['project_test_or_tool_entries'] = bad
    result['notable_modules'] = sorted(name for name in result['modules'] if name.split('.')[0] in ('unittest', 'pytest', 'PIL', 'pefile', 'ofxtools', 'controller'))
    serialized = (json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    args.output.write_bytes(serialized)
    print(f"Inventory: {args.format}, {len(result['modules'])} modules, forbidden={bad}")
    def present(prefix):
        for name in names:
            norm = name.replace('\\', '/').replace('/', '.')
            if norm == prefix or norm.startswith(prefix + '.'):
                return True
        return False
    summary = ', '.join(f'{name}={present(name)}' for name in ('unittest', 'pytest', 'PIL', 'pefile', 'test_baseline'))
    print(f'::notice title=Auditoria de empacotamento {args.format}::{len(result["modules"])} modulos; {summary}; testes proprios={len(bad)}')
    payload = base64.b64encode(gzip.compress(serialized, mtime=0)).decode('ascii')
    chunks = [payload[i:i+2000] for i in range(0, len(payload), 2000)]
    digest = hashlib.sha256(serialized).hexdigest()
    label = args.input.parent.name if args.format == 'nuitka' else 'onefile'
    for index, chunk in enumerate(chunks, 1):
        print(f'::notice title=Inventario {args.format} {label} {index}/{len(chunks)} sha256={digest}::{chunk}')
    if bad:
        raise SystemExit('Project test or tool module included in packaged application')


if __name__ == '__main__':
    main()
