"""Run the preselected arms sequentially; stop on any process/budget failure."""
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

root = Path(__file__).absolute().parents[4]
report = Path(__file__).absolute().parent
base = root / 'artifacts/system-one-pilot/adaptation-v1'
python = root / 'artifacts/system-one-pilot/compare-venv/bin/python'
base.joinpath('online').mkdir(exist_ok=True)
for arm in ['native', 'bm25', 'llm', 'frozen', 'ce', 'brier']:
    out = base / 'online' / (arm + '-v1')
    command = [str(python), '-m', 'scripts.system_one_pilot.online', 'run',
               '--arm', arm, '--protocol', str(report / 'protocol.json'),
               '--dataset', str(base / 'dataset-v1'), '--heads', str(base / 'heads-v1'),
               '--out', str(out)]
    # Existing output means a prior attempt; never silently replay it.
    with (base / 'online' / (arm + '-v1.log')).open('x') as log:
        result = subprocess.run(command, cwd=root, stdin=subprocess.DEVNULL,
                                stdout=log, stderr=subprocess.STDOUT)
    print(json.dumps({'arm': arm, 'returncode': result.returncode,
                      'at': datetime.now(timezone.utc).isoformat()}), flush=True)
    if result.returncode:
        sys.exit(result.returncode)
