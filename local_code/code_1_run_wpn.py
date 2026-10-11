"""1. Check a concentration table and run the saved WPN model on CPU."""
from pathlib import Path
import argparse
import json
from datetime import datetime, timezone
import time
from wpn_core import ROOT, CPUModel, evaluate_input, read_input, save_results, write_check

def run(input_path, output_dir):
    started = time.perf_counter()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    catalog = json.loads((ROOT / 'data/chemicals.json').read_text(encoding='utf-8'))
    checks, valid = evaluate_input(read_input(input_path), catalog)
    write_check(output_dir / 'input_check.csv', checks)
    print(f'{len(valid)} valid chemicals; {len(checks) - len(valid)} invalid rows. See input_check.csv.', flush=True)
    if not valid:
        raise ValueError(f'No valid concentrations. Edit the input table and run again. Check: {output_dir / "input_check.csv"}')
    print('Loading the saved WPN model on CPU ...', flush=True)
    model = CPUModel()
    print(f'Calculating {len(valid)} chemicals ...', flush=True)
    rows = model.predict(valid)
    save_results(output_dir / 'WPN_results.csv', rows)
    metadata = {'createdAt': datetime.now(timezone.utc).isoformat(), 'device': 'cpu', 'validChemicals': len(valid), 'invalidRows': len(checks) - len(valid), 'modelVersion': model.manifest['version'], 'elapsedSeconds': time.perf_counter() - started}
    (output_dir / 'run_info.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    print(f'Calculation complete in {metadata["elapsedSeconds"]:.1f} seconds.', flush=True)
    return output_dir

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / 'inputs/concentrations.xlsx')
    parser.add_argument('--output', type=Path, default=ROOT / 'results' / datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    args = parser.parse_args()
    run(args.input, args.output)
