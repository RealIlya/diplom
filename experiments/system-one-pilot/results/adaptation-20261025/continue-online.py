"""Continue only after reconciliation; preserve prior failed attempts verbatim."""
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

root = Path(__file__).absolute().parents[4]
sys.path.insert(0,str(root))
from scripts.system_one_pilot.live_api import PaidClient
from scripts.system_one_pilot.compare import filehash

report = Path(__file__).absolute().parent
base = root/'artifacts/system-one-pilot/adaptation-v1'
python = root/'artifacts/system-one-pilot/compare-venv/bin/python'
client = PaidClient(root/'artifacts/system-one-pilot/authorized-series-20261025.sqlite3','collection')
if client.summary()['unresolved']:
    raise SystemExit('Unknown outcome still blocks series; no continuation executed')
proposal=json.loads((report/'online-continuation-proposal.json').read_text())
prior=base/'online/frozen-v1'
assert filehash(prior/'receipt.json') == proposal['prior_receipt_sha256']
for task,sha in proposal['prior_files_sha256'].items():assert filehash(prior/(task+'.json')) == sha

for arm,version in [('frozen',2),('ce',1),('brier',1)]:
    name=arm+'-v'+str(version)
    command=[str(python),'-m','scripts.system_one_pilot.online','run','--arm',arm,
             '--protocol',str(report/'protocol.json'),'--dataset',str(base/'dataset-v1'),
             '--heads',str(base/'heads-v1'),'--out',str(base/'online'/name)]
    if arm=='frozen':command+=['--continue-from',str(prior)]
    with (base/'online'/(name+'.log')).open('x') as log:
        result=subprocess.run(command,cwd=root,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
    print(json.dumps({'arm':arm,'returncode':result.returncode,'at':datetime.now(timezone.utc).isoformat()}),flush=True)
    if result.returncode:sys.exit(result.returncode)
