"""Verify local snapshots without fitting models or writing evaluation evidence."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha256(stream):
    value = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        value.update(chunk)
    return value.hexdigest()


def verify_manifest(path, root=ROOT, included_only=False, history_only=False):
    checked = 0
    with Path(path).open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError('Empty manifest')
    for row in rows:
        if history_only and row['file'] not in {
            'data/raw/international_results_current.zip', 'data/raw/fjelstul_worldcup.zip',
            'reports/probabilistic/resolved_fixtures.csv',
        }:
            continue
        if included_only and row['included_in_git'] != 'yes':
            continue
        file = (root / row['file']).resolve()
        if not file.is_relative_to(root.resolve()):
            raise ValueError('Manifest path outside repository')
        member = row['archive_member']
        if member:
            with zipfile.ZipFile(file) as archive, archive.open(member) as stream:
                actual = sha256(stream)
                size = archive.getinfo(member).file_size
        else:
            with file.open('rb') as stream:
                actual = sha256(stream)
            size = file.stat().st_size
        if actual != row['sha256'] or size != int(row['bytes']):
            raise ValueError(f"Snapshot mismatch: {row['file']}::{member}")
        checked += 1
    return checked


def rebuild_history():
    # Data processing only: no feature-state updates, model fitting or metrics.
    sys.path[:0] = [str(ROOT / 'src'), str(ROOT / '.deps')]
    from football_forecast.ingestion import load_study_data
    inventory = json.loads((ROOT / 'reports/final_evaluation/data_inventory.json').read_text(encoding='utf-8'))
    study = load_study_data(ROOT, cutoff='2026-06-10')
    history = study.history
    # The audited CSV was produced on Windows. Keep its exact CRLF serialization.
    actual_hash = hashlib.sha256(history.to_csv(index=False, lineterminator='\r\n').encode('utf-8')).hexdigest()
    if actual_hash != inventory['history_sha256']:
        raise ValueError(f"history_sha256 mismatch: {actual_hash}")
    counts = {
        'history_matches': len(history),
        'model_training_matches': int((history.date.ge('2000-01-01') & history.date.lt('2023-01-01')).sum()),
        'pre2023_walk_forward_matches': int((history.date.ge('2016-01-01') & history.date.lt('2023-01-01')).sum()),
        'semiconfirmatory_matches': int(history.date.ge('2023-01-01').sum()),
        'group_forecasts': len(study.fixtures),
    }
    for key, actual in counts.items():
        if actual != inventory[key]:
            raise ValueError(f'Count mismatch: {key}: {actual} != {inventory[key]}')
    return {'history_sha256': actual_hash, **counts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'data/MANIFEST.csv')
    parser.add_argument('--included-only', action='store_true', help='Check only currently tracked sources; not full reproduction')
    parser.add_argument('--history-only', action='store_true', help='Verify only the three inputs needed to rebuild historical data')
    parser.add_argument('--rebuild-history', action='store_true', help='Reconstruct in memory and verify audited hash/counts; no models')
    args = parser.parse_args()
    try:
        if args.included_only and args.history_only:
            parser.error('Choose one verification scope')
        checked = verify_manifest(args.manifest, included_only=args.included_only, history_only=args.history_only)
        from verify_final_evaluation import frozen_checks
        frozen = frozen_checks()
        result = {'snapshots_checked': checked, 'scope': 'history_only' if args.history_only else 'included_only' if args.included_only else 'all_local_sources',
                  'frozen_artifacts_checked': frozen['frozen_artifacts_checked'],
                  'protected_code_files_checked': frozen['protected_code_files_checked'], 'models_rerun': False}
        if args.rebuild_history:
            result.update(rebuild_history())
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as error:
        parser.exit(1, f'ERROR: {error}\n')


if __name__ == '__main__':
    main()
