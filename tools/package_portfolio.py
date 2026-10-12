"""Package authored source and generated results, without private/raw archives."""
from pathlib import Path
import zipfile
import subprocess

root=Path(__file__).resolve().parents[1]
git=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
command=str(git) if git.exists() else 'git'
tracked=subprocess.check_output([command,'ls-files','-z'],cwd=root).decode('utf-8').split('\0')
target=root/'portfolio_github.zip'
with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
    for name in sorted(filter(None,tracked)):
        path=root/name
        if name.startswith('data/raw/'):
            raise RuntimeError('Raw sources must not be packaged automatically')
        if path.is_file(): archive.write(path,name)
print(f'Portfolio package: {target.name} ({target.stat().st_size:,} bytes)')
