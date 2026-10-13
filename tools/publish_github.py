"""Publish the approved frozen study using Git's existing credential manager.

Credentials remain in memory and are never logged or persisted by this tool.
No model pipeline is executed.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['prepare','deploy','status'])
    parser.add_argument('--owner',default='Madsh26')
    parser.add_argument('--repository',default='elo-vs-ml-futbol-selecciones')
    args=parser.parse_args()
    executable=shutil.which('git') or str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')
    process=subprocess.run([executable,'credential','fill'],input=f'protocol=https\nhost=github.com\nusername={args.owner}\n\n',
                           text=True,capture_output=True,check=True,
                           env=dict(os.environ,GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='never'))
    credential=dict(line.split('=',1) for line in process.stdout.splitlines() if '=' in line)
    token=credential['password']

    def api(path,method='GET',body=None):
        request=urllib.request.Request('https://api.github.com/'+path,method=method,
            data=json.dumps(body).encode('utf-8') if body is not None else None,
            headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json',
                     'X-GitHub-Api-Version':'2022-11-28','User-Agent':'frozen-study-publication','Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(request,timeout=45) as response:
                content=response.read()
                return json.loads(content) if content else {}
        except urllib.error.HTTPError as error:
            if error.code==404:return None
            # GitHub error response contains no request authorization headers.
            raise RuntimeError(f'GitHub HTTP {error.code}: '+error.read().decode('utf-8')) from None

    user=api('user')
    if user['login'].casefold()!=args.owner.casefold():raise RuntimeError('Authenticated account differs from requested owner')
    repository=f'repos/{args.owner}/{args.repository}'
    if args.stage=='prepare':
        if api(repository) is not None:raise RuntimeError('Repository already exists; refusing to replace or reset it')
        result=api('user/repos','POST',{'name':args.repository,'description':'Evaluación retrospectiva de Elo, machine learning y modelos de goles en fútbol de selecciones.',
                                      'private':False,'auto_init':False,'homepage':f'https://{args.owner.lower()}.github.io/{args.repository}/'})
        # Suppress tag-triggered historical workflows during the first upload.
        api(repository+'/actions/permissions','PUT',{'enabled':False})
        api(repository+'/topics','PUT',{'names':['sports-analytics','elo-rating','xgboost','probabilistic-forecasting','reproducible-research']})
        print(json.dumps({'repository':result['html_url'],'visibility':'public','actions_during_initial_upload':'disabled','models_executed':False}))
    elif args.stage=='deploy':
        api(repository+'/actions/permissions','PUT',{'enabled':True,'allowed_actions':'all'})
        pages=api(repository+'/pages')
        if pages is None:pages=api(repository+'/pages','POST',{'build_type':'legacy','source':{'branch':'main','path':'/'}})
        api(repository+'/actions/workflows/tests.yml/dispatches','POST',{'ref':'main'})
        print(json.dumps({'pages_url':pages.get('html_url'),'pages_status':pages.get('status'),'source':pages.get('source'),'models_executed':False}))
    else:
        pages=api(repository+'/pages') or {}
        workflows=api(repository+'/actions/runs?per_page=8') or {}
        print(json.dumps({'pages_url':pages.get('html_url'),'pages_status':pages.get('status'),
                          'workflows':[{'id':r['id'],'name':r['name'],'status':r['status'],'conclusion':r['conclusion'],'url':r['html_url']} for r in workflows.get('workflow_runs',[])]}))


if __name__=='__main__':main()
