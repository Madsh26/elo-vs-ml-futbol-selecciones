"""Read-only frozen-state checks; tests write only the new evaluation folder."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
FROZEN_COMMIT='329769628f1d8a43d912cd969e5f6b3f870acaef'
OUTPUT=ROOT/'reports/final_evaluation'


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(*args):
    executable=shutil.which('git')
    fallback=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
    if executable is None and fallback.exists():executable=str(fallback)
    if executable is None:raise RuntimeError('Git required to verify the authoritative frozen snapshot')
    return subprocess.check_output([executable,*args],cwd=ROOT)


def frozen_checks():
    resolved=git('rev-parse','models-selected^{commit}').decode().strip()
    if resolved!=FROZEN_COMMIT:raise ValueError('models-selected does not point to 3297696')
    committed=json.loads(git('show',f'{FROZEN_COMMIT}:data_audit.json'))
    hashes=committed['artifacts_models_selected']
    for relative,expected in hashes.items():
        if digest(ROOT/relative)!=expected:raise ValueError(f'Frozen artifact changed: {relative}')
    folder=ROOT/'reports/models_selected'
    expected_files=set(hashes)|{'reports/models_selected/data_audit.json'}
    actual_files={p.relative_to(ROOT).as_posix() for p in folder.iterdir() if p.is_file()}
    if actual_files!=expected_files:raise ValueError('Frozen artifact inventory changed')
    if (folder/'data_audit.json').read_bytes()!=git('show',f'{FROZEN_COMMIT}:reports/models_selected/data_audit.json'):
        raise ValueError('Frozen audit changed')
    manifest=json.loads((folder/'freeze_manifest.json').read_text(encoding='utf-8'))
    if digest(folder/'protocol.json')!=manifest['protocol_sha256']:raise ValueError('Frozen protocol changed')
    for path,expected in manifest['code_sha256'].items():
        normalized=hashlib.sha256((ROOT/path).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
        if normalized!=expected:raise ValueError(f'Protected code changed: {path}')
    return {'verified_at_utc':utc_now(),'models_selected_commit':resolved,
            'models_selected_commit_time':git('show','-s','--format=%cI',FROZEN_COMMIT).decode().strip(),
            'freeze_manifest_sha256':digest(folder/'freeze_manifest.json'),
            'model_selection_protocol_sha256':digest(folder/'protocol.json'),
            'frozen_artifacts_checked':len(actual_files),'protected_code_files_checked':len(manifest['code_sha256']),
            'reserved_metrics_computed':False}


def protocol_checks(require_tag=False):
    if (OUTPUT/'active_protocol.json').exists():
        seal=json.loads((OUTPUT/'active_protocol.json').read_text(encoding='utf-8'))
        path=ROOT/seal['protocol_file']
        if digest(path)!=seal['protocol_sha256']:raise ValueError('Approved protocol changed')
        if digest(ROOT/seal['human_protocol_file'])!=seal['human_protocol_sha256']:raise ValueError('Approved human protocol changed')
        result={'protocol_file':seal['protocol_file'],'protocol_sha256':seal['protocol_sha256'],'sealed_at_utc':seal['sealed_at_utc']}
        if require_tag:
            commit=git('rev-parse',seal['git_tag']+'^{commit}').decode().strip()
            if path.read_bytes()!=git('show',f"{commit}:{seal['protocol_file']}"):raise ValueError('Approved protocol differs from tag')
            result.update(protocol_commit=commit,protocol_commit_time=git('show','-s','--format=%cI',commit).decode().strip())
        return result
    seal=json.loads((OUTPUT/'protocol_seal.json').read_text(encoding='utf-8'))
    if digest(OUTPUT/'protocol.json')!=seal['protocol_sha256']:raise ValueError('Evaluation protocol changed after sealing')
    if 'human_protocol_sha256' in seal and digest(OUTPUT/'PROTOCOLO.md')!=seal['human_protocol_sha256']:
        raise ValueError('Human-readable protocol changed after sealing')
    if require_tag:
        commit=git('rev-parse','phase4-protocol^{commit}').decode().strip()
        if (OUTPUT/'protocol.json').read_bytes()!=git('show',f'{commit}:reports/final_evaluation/protocol.json'):
            raise ValueError('Evaluation protocol differs from phase4-protocol tag')
        return {'protocol_commit':commit,'protocol_commit_time':git('show','-s','--format=%cI',commit).decode().strip()}
    return {'protocol_sha256':seal['protocol_sha256'],'sealed_at_utc':seal['sealed_at_utc']}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check-only',action='store_true')
    parser.add_argument('--require-tag',action='store_true')
    args=parser.parse_args()
    checks=frozen_checks()
    checks.update(protocol_checks(args.require_tag))
    if (OUTPUT/'predictions_seal.json').exists():
        sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'.deps')]
        from run_final_evaluation import check_prediction_commit
        checks.update(check_prediction_commit())
    if (OUTPUT/'data_audit.json').exists():
        final_audit=json.loads((OUTPUT/'data_audit.json').read_text(encoding='utf-8'))
        from seal_presentation import verify_revision
        for relative,expected in final_audit['output_sha256'].items():
            if digest(ROOT/relative)!=expected and not verify_revision(relative,expected):raise ValueError(f'Final evidence changed: {relative}')
        for relative,expected in final_audit['documentation_sha256'].items():
            if digest(ROOT/relative)!=expected and not verify_revision(relative,expected):raise ValueError(f'Documentation changed: {relative}')
        checks['final_evidence_hashes_checked']=len(final_audit['output_sha256'])
    if args.check_only:
        print(json.dumps(checks,ensure_ascii=False,indent=2));return
    for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ.setdefault(name,'2')
    # The DataCamp reproduction is excluded, including after approval.
    os.environ.pop('ALLOW_RESERVED_EVALUATION',None)
    sys.path[:0]=[str(ROOT/'src'),str(ROOT/'.deps')]
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    verification={**checks,'executed_at_utc':utc_now(),'tests_run':result.testsRun,
        'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
        'skip_reasons':[reason for _,reason in result.skipped],'successful':result.wasSuccessful(),
        'command':'python tools/verify_final_evaluation.py',
        'stage':'evaluation completed' if (OUTPUT/'worldcup_conclusion.json').exists() else 'protocol or prediction stage'}
    verification['skipped_missing_local_data']=sum(any(token in reason.lower() for token in
        ['local inputs','local archives','local executed feature','raw data']) for _,reason in result.skipped)
    verification['skipped_historical_exclusion']=sum('DataCamp' in reason for _,reason in result.skipped)
    verification.pop('reserved_metrics_computed',None)
    verification['integrity_check_computed_metrics']=False
    verification['post2022_evaluation_executed']=(OUTPUT/'worldcup_conclusion.json').exists()
    print(f"Pruebas: {result.testsRun}; omitidas por datos locales: {verification['skipped_missing_local_data']}; exclusión histórica: {verification['skipped_historical_exclusion']}")
    (OUTPUT/'verification.json').write_text(json.dumps(verification,indent=2,ensure_ascii=False),encoding='utf-8')
    # Check again: neither tests nor verification may mutate frozen artifacts.
    frozen_checks()
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__=='__main__':main()
