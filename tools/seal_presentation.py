"""Record permitted presentation changes without rewriting evaluation audits."""
import argparse
import json
from pathlib import Path
from verify_final_evaluation import digest, frozen_checks, git, utc_now

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {'README.md', 'reports/final_evaluation/football_report.html',
           'reports/final_evaluation/html_review.json', 'reports/final_evaluation/report_manifest.json'}


def verify_revision(relative, original):
    if relative not in ALLOWED:
        return False
    ledger_path = ROOT / 'docs/presentation_revisions.json'
    if not ledger_path.exists():
        return False
    ledger = json.loads(ledger_path.read_text(encoding='utf-8'))
    entry = ledger['current'].get(relative, {})
    return (entry.get('evaluation_sha256') == original and
            entry.get('current_sha256') == digest(ROOT / relative) and
            ledger['evaluation_commit'] == git('rev-parse', 'phase4-evaluated^{commit}').decode().strip())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', required=True)
    parser.add_argument('files', nargs='+', choices=sorted(ALLOWED))
    args = parser.parse_args()
    frozen_checks()
    commit = git('rev-parse', 'phase4-evaluated^{commit}').decode().strip()
    audit = json.loads(git('show', commit + ':reports/final_evaluation/data_audit.json'))
    original = {**audit['output_sha256'], **audit['documentation_sha256']}
    path = ROOT / 'docs/presentation_revisions.json'
    ledger = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {
        'evaluation_commit': commit, 'current': {}, 'events': []}
    changed = {}
    for relative in args.files:
        entry = {'evaluation_sha256': original[relative], 'current_sha256': digest(ROOT / relative)}
        ledger['current'][relative] = entry
        changed[relative] = entry
    ledger['events'].append({'recorded_at_utc': utc_now(), 'stage': args.stage,
                             'presentation_after_evaluation': True, 'models_rerun': False,
                             'metrics_protocols_conclusions_changed': False, 'files': changed})
    path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding='utf-8')
    print('Presentation revision recorded; historical evaluation audit retained.')


if __name__ == '__main__':
    main()
