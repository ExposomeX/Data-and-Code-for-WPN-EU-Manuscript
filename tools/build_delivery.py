"""Package the maintained website for a different Windows computer.

Excludes local environments, development evidence and user runs. Blank input
templates are read from the separately maintained CPU download ZIP. No local
input file, result or scientific artifact is overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {'.runtime', '.venv', 'node_modules', '__pycache__', '.git', '验收截图'}
PROCESS_FILES = {
    '改版说明.md', '化合物目录核验报告.md', '浏览器验收_20261009.md',
    '数据核验报告.md', '验收记录.md', '验收记录.json', '资源与下载验收.json',
    'backend-validation.md', 'backend-validation.json', 'Code与表格改版验收_20261009.md',
    'cpu-clean-environment-validation.json', 'cpu-package-validation.json',
    'subset-validation.md', 'subset-validation.json', '材料与版本说明.md',
    '内容来源说明.md', 'local_code/VALIDATION.md',
}


def delivery_files():
    """Prune installed environments before traversal; never follow outside links."""
    for folder, directories, files in os.walk(ROOT, followlinks=False):
        directories[:] = sorted(name for name in directories
                                if name not in EXCLUDED_DIRS
                                and not (Path(folder) / name).is_symlink()
                                and not (Path(folder) / name).is_junction())
        for name in sorted(files):
            path = Path(folder) / name
            if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
                raise RuntimeError(f'Delivery files must be inside the project: {path}')
            yield path


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT.parent / 'WPN-Windows-CPU.zip')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(ROOT):
        parser.error('Write the delivery ZIP outside the source directory.')
    code_zip = ROOT / 'public/downloads/WPN-local-code.zip'
    served_zip = ROOT / 'dist/downloads/WPN-local-code.zip'
    if not (ROOT / 'dist/index.html').is_file() or not served_zip.is_file() or digest(code_zip) != digest(served_zip):
        raise RuntimeError('Rebuild the website after publishing the CPU package, then retry.')
    templates = {'local_code/inputs/concentrations.xlsx': 'WPN-local-code/inputs/concentrations.xlsx',
                 'local_code/inputs/concentrations.csv': 'WPN-local-code/inputs/concentrations.csv'}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='wpn-delivery-') as folder, ZipFile(code_zip) as source:
        temporary = Path(folder) / output.name
        with ZipFile(temporary, 'w', ZIP_DEFLATED, compresslevel=6) as archive:
            for path in delivery_files():
                relative = path.relative_to(ROOT)
                name = relative.as_posix()
                if path.suffix in {'.pyc', '.pyo', '.log'} or name in PROCESS_FILES or name in templates:
                    continue
                if name.startswith('local_code/results/') and name != 'local_code/results/README.txt':
                    continue
                if name.startswith('local_code/inputs/'):
                    continue
                archive.write(path, 'WPN/' + name)
            for name, source_name in templates.items():
                archive.writestr('WPN/' + name, source.read(source_name))
        # Copy beside the destination before replace so cross-volume moves work.
        staged = output.with_name(output.name + '.tmp')
        import shutil
        shutil.copyfile(temporary, staged)
        staged.replace(output)
    checksum = digest(output)
    output.with_suffix(output.suffix + '.sha256').write_text(f'{checksum}  {output.name}\n', encoding='utf-8')
    print(f'{output}\n{output.stat().st_size:,} bytes\nSHA256 {checksum}')


if __name__ == '__main__':
    main()
