"""Compare the local CPU package with an already running WPN website.

This opt-in check performs real inference; it never starts or stops the website.
Run with the installed CPU environment. JSON goes to stdout by default.
"""
import argparse
from contextlib import redirect_stdout
import importlib.metadata
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def request(base_url, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(base_url.rstrip('/') + path, data=data,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def load_core(package):
    source = package / 'wpn_core.py'
    if not source.is_file():
        raise ValueError(f'Expected a CPU package directory containing wpn_core.py: {package}')
    spec = importlib.util.spec_from_file_location('wpn_validation_core', source)
    core = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = core
    spec.loader.exec_module(core)
    return core


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, default=ROOT / 'local_code',
                        help='CPU package directory (default: this delivery\'s local_code).')
    parser.add_argument('--website-url', default='http://127.0.0.1:4174',
                        help='Already running website to compare; no historical snapshot is required.')
    parser.add_argument('--timeout', type=float, default=300, help='Maximum website job wait in seconds.')
    parser.add_argument('--log10-tolerance', type=float, default=.005,
                        help='Numerical replay tolerance, not scientific prediction uncertainty.')
    parser.add_argument('--report', type=Path, help='Also write JSON to this explicitly requested path.')
    args = parser.parse_args(argv)
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error('--timeout must be finite and positive')
    if not math.isfinite(args.log10_tolerance) or args.log10_tolerance < 0:
        parser.error('--log10-tolerance must be finite and nonnegative')
    package = args.package.resolve()
    core = load_core(package)
    catalog = json.loads((package / 'data/chemicals.json').read_text(encoding='utf-8'))
    checks, valid = core.evaluate_input(core.read_input(package / 'examples/example_52.csv'), catalog)
    assert len(valid) == 52 and all(row['valid'] for row in checks)
    health = request(args.website_url, '/api/health')
    assert health['status'] == 'ready', health
    job = request(args.website_url, '/api/runs', {
        'inputs': [{'chemical': row['chemical'], 'ww': row['value'], 'origin': 'example'} for row in valid]
    })
    started = time.monotonic()
    while True:
        job = request(args.website_url, '/api/runs/' + job['id'])
        if job['status'] in {'succeeded', 'failed'}:
            assert job['status'] == 'succeeded', job
            break
        if time.monotonic() - started > args.timeout:
            raise RuntimeError(f'The website calculation did not finish within {args.timeout:g} seconds.')
        time.sleep(.3)
    website = {row['chemical']: row for row in job['result']['rows']}
    assert set(website) == {row['chemical'] for row in valid}
    assert all(math.isfinite(row['beq']) and row['beq'] > 0 for row in website.values())
    started = time.perf_counter()
    with redirect_stdout(sys.stderr):
        model = core.CPUModel()
    load_seconds = time.perf_counter() - started
    assert all(str(device) == 'cpu' for device in model.estimator.devices_)
    assert not model.torch.cuda.is_initialized() and not model.torch.cuda.is_available()
    scenarios = []
    for count in (52, 10, 1):
        start = time.perf_counter()
        with redirect_stdout(sys.stderr):
            rows = model.predict(valid[:count])
        duration = time.perf_counter() - start
        assert len(rows) == count and {row['chemical'] for row in rows} == {row['chemical'] for row in valid[:count]}
        assert all(math.isfinite(row['beq']) and row['beq'] > 0 for row in rows)
        assert math.isclose(sum(row['contribution'] for row in rows), 100., abs_tol=1e-10)
        assert all(row['rank'] == 1 + sum(other['beq'] > row['beq'] for other in rows) for row in rows)
        relative = max(abs(row['beq'] / website[row['chemical']]['beq'] - 1.) for row in rows)
        log_difference = max(abs(math.log10(row['beq']) - math.log10(website[row['chemical']]['beq'])) for row in rows)
        assert log_difference <= args.log10_tolerance, log_difference
        entry = {'count': count, 'seconds': duration,
                 'maxRelativeBEQDifferenceVsWebsite52': relative,
                 'maxLog10BEQDifferenceVsWebsite52': log_difference}
        if count == 52:
            entry['sameRankAsWebsite52'] = all(row['rank'] == website[row['chemical']]['beqRank'] for row in rows)
            entry['maxContributionPercentagePointDifference'] = max(
                abs(row['contribution'] - website[row['chemical']]['beqContribution']) for row in rows)
            assert entry['sameRankAsWebsite52']
        scenarios.append(entry)
        print(f'Validated {count} chemicals.', file=sys.stderr, flush=True)
    report = {
        'status': 'passed', 'createdAt': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'packagePath': str(package), 'cpuLoadSeconds': load_seconds,
        'websiteUrl': args.website_url, 'websiteRunId': job['id'],
        'websiteModelVersion': health.get('modelVersion'),
        'log10Tolerance': args.log10_tolerance, 'scenarios': scenarios,
        'cpuDevice': str(model.estimator.devices_), 'cudaInitialized': model.torch.cuda.is_initialized(),
        'runtime': {key: importlib.metadata.version(key) for key in
                    ['torch', 'tabpfn', 'numpy', 'pandas', 'scikit-learn', 'joblib', 'matplotlib', 'openpyxl']},
        'python': sys.version,
    }
    text = json.dumps(report, indent=2)
    if args.report:
        output = args.report.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + '\n', encoding='utf-8')
    print(text)
    return report


if __name__ == '__main__':
    main()
