"""Offline trusted export; preserve old dataset roles and every frozen denominator."""
import collections
import json
from pathlib import Path
from scripts.system_one_pilot.live import ROOT, BUDGET_DB, SPLIT, read_jsonl, save_jsonl
from scripts.system_one_pilot.live_api import PaidClient, daily_summary, utc
from scripts.system_one_pilot.compare import filehash
from scripts.system_one_pilot.data import write_json
from scripts.system_one_pilot.expansion import merge_labeled
from scripts.system_one_pilot.review import import_run

report=Path(__file__).absolute().parent
protocol=json.loads((report/'protocol.json').read_text())
root=ROOT/protocol['root'];oldbase=ROOT/'artifacts/system-one-pilot/adaptation-v1'
for path,expected in [(SPLIT,protocol['split_sha256']),
                      (oldbase/'dataset-v1/dataset.jsonl',protocol['old_dataset_sha256']),
                      (oldbase/'trusted-labels-v1.jsonl',protocol['old_trusted_sha256'])]:
    if filehash(path)!=expected:raise ValueError('frozen source changed: '+str(path))
queue=read_jsonl(root/'queue.jsonl')
if filehash(root/'queue.jsonl')!=json.loads((report/'queue-summary.json').read_text())['queue_sha256']:
    raise ValueError('queue changed')
answers=[json.loads(p.read_text()) for p in sorted((root/'annotations-v2').glob('*.json'))]
counts=collections.Counter(a['row_id'] for a in answers)
if set(counts)!={r['id'] for r in queue} or set(counts.values())!={2}:
    raise ValueError('incomplete paired annotations; retain original denominator')
series={s:PaidClient(BUDGET_DB,s).summary() for s in protocol['series_caps_nusd']}
if any(v['unresolved'] for v in series.values()):raise ValueError('unresolved paid outcomes')
adjudications={}
for path in sorted((root/'adjudication').glob('batch-*-decisions.json')):
    batch=json.loads(path.read_text())
    if set(batch)&set(adjudications):raise ValueError('duplicate adjudication')
    adjudications.update(batch)
store=import_run(root,root/'trusted-review-v1.sqlite3',annotation_version=2)
store.accept_models(adjudications)
labels=store.export()
if {r['row_id'] for r in labels}!={r['id'] for r in queue}:raise ValueError('incomplete trusted export')
old=read_jsonl(oldbase/'dataset-v1/dataset.jsonl')
combined=merge_labeled(old,labels,json.loads(SPLIT.read_text()))
out=root/'dataset-v1';out.mkdir(exist_ok=False)
save_jsonl(out/'new-trusted-labels.jsonl',labels)
save_jsonl(out/'dataset.jsonl',combined)
def stats(rows):
    hard=[r for r in rows if r['label']!='uncertain' and not r['defect']]
    return dict(rows=len(rows),hard=len(hard),families=len({r['family'] for r in rows}),
                labels=dict(collections.Counter(r['label'] for r in rows)),
                hard_labels=dict(collections.Counter(r['label'] for r in hard)),
                defects=sum(r['defect'] for r in rows),
                sources=dict(collections.Counter(r['label_source'] for r in rows)))
new=combined[len(old):]
manifest=dict(at=utc(),protocol_sha256=filehash(report/'protocol.json'),
    queue_sha256=filehash(root/'queue.jsonl'),old_dataset_sha256=protocol['old_dataset_sha256'],
    old_trusted_sha256=protocol['old_trusted_sha256'],split_sha256=protocol['split_sha256'],
    new_labels_sha256=filehash(out/'new-trusted-labels.jsonl'),dataset_sha256=filehash(out/'dataset.jsonl'),
    new=stats(new),combined=stats(combined),
    roles={role:stats([r for r in combined if r['role']==role]) for role in sorted({r['role'] for r in combined})},
    resolutions=dict(collections.Counter(r['resolution']['source'] for r in labels)),
    annotation_statuses=dict(collections.Counter(r['status'] for r in answers)),
    family_counts=dict(collections.Counter(r['family'] for r in new)),
    unchanged_old_rows=combined[:len(old)]==old, test_rows=0,
    series_budget=series,daily_budget=daily_summary(BUDGET_DB),
    scope='train-only engineering packet; no new independent validation or model quality claim',
    training_run=False,human_review=False)
write_json(out/'manifest.json',manifest)
write_json(report/'dataset-summary.json',dict(manifest,artifact_root=str(out.relative_to(ROOT))))
store.backup(root/'trusted-review-v1-backup.sqlite3')
print(json.dumps(manifest,ensure_ascii=False,indent=2))
