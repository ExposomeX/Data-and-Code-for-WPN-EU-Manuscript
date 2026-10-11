"""Relocate a CPU package and run its example with network access disabled.

Accepts a package directory or ZIP; defaults to this delivery's local_code.
Use the installed CPU-only Python environment. Temporary calculation outputs
are removed with the relocated copy. JSON is printed; --report saves it only
when explicitly requested. This check does not install dependencies.
"""
import argparse
from contextlib import contextmanager, redirect_stdout
import importlib.metadata
import json
import os
from pathlib import Path
import runpy
import shutil
import stat
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def find_package(directory):
    candidates = [directory, directory / 'local_code', directory / 'WPN-local-code']
    matches = [path for path in candidates if (path / 'run.py').is_file() and (path / 'wpn_core.py').is_file()]
    if len(matches) != 1:
        raise ValueError(f'Expected one CPU package containing run.py and wpn_core.py under {directory}')
    return matches[0].resolve()


def extract_package(archive, destination):
    with zipfile.ZipFile(archive) as bundle:
        for entry in bundle.infolist():
            target = (destination / entry.filename).resolve()
            if not target.is_relative_to(destination.resolve()) or stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError(f'Unsafe ZIP member: {entry.filename}')
        bundle.extractall(destination)


@contextmanager
def relocated_package(source):
    source = source.resolve()
    with tempfile.TemporaryDirectory(prefix='WPN CPU validation ') as temporary:
        destination = Path(temporary) / '独立运行 with spaces'
        if source.is_dir():
            original = find_package(source)
            shutil.copytree(original, destination, symlinks=True,
                            ignore=shutil.ignore_patterns('.venv', '__pycache__', 'results', '.runtime', '.git'))
            blocked = [original]
        elif source.is_file() and zipfile.is_zipfile(source):
            destination.mkdir()
            extract_package(source, destination)
            blocked = []
        else:
            raise ValueError(f'Package must be an existing directory or ZIP: {source}')
        package = find_package(destination)
        if any(path.is_symlink() for path in package.rglob('*')):
            raise ValueError('The relocated package contains a symbolic link to an external resource.')
        yield package, blocked


class OfflineGuard:
    """Audit Python network calls and accesses to non-relocated model artifacts."""
    def __init__(self, package, blocked_paths):
        self.package = package.resolve()
        self.blocked_paths = [path.resolve() for path in blocked_paths]
        self.network_attempts = []
        self.external_artifact_attempts = []
        self.enabled = False

    def __call__(self, event, args):
        if not self.enabled:
            return
        if event in {'socket.connect', 'socket.getaddrinfo', 'socket.gethostbyname',
                     'socket.gethostbyaddr', 'socket.sendto', 'socket.sendmsg'}:
            self.network_attempts.append(event)
            raise RuntimeError('Network access is disabled for the offline package verification.')
        if event == 'open' and args and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0])).resolve()
            blocked = any(path.is_relative_to(root) for root in self.blocked_paths)
            model_artifact = path.suffix.lower() in {'.joblib', '.ckpt'} or path.name in {
                'parameters.csv', 'chemicals.json', 'feature_columns.csv', 'feature_preprocessing.csv'}
            if blocked or (model_artifact and not path.is_relative_to(self.package)):
                self.external_artifact_attempts.append(str(path))
                raise RuntimeError(f'The package attempted to access a non-relocated artifact: {path}')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, default=ROOT / 'local_code', help='CPU package directory or ZIP.')
    parser.add_argument('--input', type=Path, help='Optional input file; copied into the relocated package before execution.')
    parser.add_argument('--forbid-path', action='append', type=Path, default=[],
                        help='Additional source directory that the package must not access; repeatable.')
    parser.add_argument('--report', type=Path, help='Also write JSON to this explicitly requested path.')
    args = parser.parse_args(argv)
    source = args.package.resolve()
    with relocated_package(source) as (package, blocked):
        input_path = package / 'examples/example_52.xlsx'
        if args.input:
            input_path = package / ('validation-input' + args.input.suffix)
            shutil.copy2(args.input.resolve(), input_path)
        if not input_path.is_file():
            parser.error(f'Input file is unavailable: {input_path}')
        guard = OfflineGuard(package, blocked + [ROOT / 'local_code'] + args.forbid_path)
        sys.addaudithook(guard)
        original_argv, original_path, original_cwd = sys.argv, sys.path[:], Path.cwd()
        started = time.perf_counter()
        try:
            sys.path.insert(0, str(package))
            sys.argv = [str(package / 'run.py'), '--input', str(input_path)]
            os.chdir(package)
            guard.enabled = True
            with redirect_stdout(sys.stderr):
                try:
                    runpy.run_path(str(package / 'run.py'), run_name='__main__')
                except SystemExit as exit_status:
                    if exit_status.code not in (None, 0):
                        raise RuntimeError(f'The package exited with status {exit_status.code}.') from exit_status
            import torch
            assert torch.version.cuda is None and not torch.cuda.is_initialized()
            assert not guard.network_attempts, guard.network_attempts
            assert not guard.external_artifact_attempts, guard.external_artifact_attempts
            info = {
                'status': 'passed', 'secondsIncludingPlots': time.perf_counter() - started,
                'sourcePackage': str(source), 'relocatedIntoTemporaryDirectory': True,
                'networkAttempts': guard.network_attempts,
                'externalArtifactAttempts': guard.external_artifact_attempts,
                'torch': torch.__version__, 'torchCuda': torch.version.cuda,
                'cudaInitialized': torch.cuda.is_initialized(), 'python': sys.version,
                'dependencies': {name: importlib.metadata.version(name) for name in
                                 ['tabpfn', 'numpy', 'pandas', 'scikit-learn', 'scipy', 'matplotlib', 'openpyxl']},
            }
        finally:
            guard.enabled = False
            sys.argv, sys.path = original_argv, original_path
            os.chdir(original_cwd)
    text = json.dumps(info, indent=2)
    if args.report:
        output = args.report.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + '\n', encoding='utf-8')
    print(text)
    return info


if __name__ == '__main__':
    main()
