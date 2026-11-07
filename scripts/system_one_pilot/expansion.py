"""First bounded train-only data packet; old datasets remain immutable."""
import argparse
import collections
import json
from pathlib import Path
from types import SimpleNamespace
from .data import digest,write_json
from .compare import filehash


def task_plan(manifest,existing_families,seed=25):
    groups=collections.defaultdict(list)
    for tid,v in manifest['tasks'].items():
        if v['split']=='train' and v['family'] not in existing_families:groups[v['family']].append(tid)
    return [min(groups[f],key=lambda t:digest([seed,f,t]))
            for f in sorted(groups,key=lambda f:digest([seed,f]))]


def choose_new_cards(rows,old,target=200):
    ids={r['id'] for r in old};inputs={r['input_sha256'] for r in old}
    pairs={(r['snapshot_id'],r['document_id']) for r in old}
    families=collections.defaultdict(list)
    for r in sorted(rows,key=lambda r:digest([25,r['id']])):
        pair=(r['snapshot_id'],r['document_id'])
        if r['split']!='train' or r['admission']!='accepted' or r['id'] in ids or r['input_sha256'] in inputs or pair in pairs:continue
        ids.add(r['id']);inputs.add(r['input_sha256']);pairs.add(pair)
        families[r['family']].append(r)
    selected=[];snap_counts=collections.Counter()
    while len(selected)<target and any(families.values()):
        for family in sorted(families,key=lambda f:digest([25,f])):
            if len(selected)>=target:break
            while families[family]:
                r=families[family].pop(0)
                if snap_counts[r['snapshot_id']]>=20:continue
                selected.append(r);snap_counts[r['snapshot_id']]+=1;break
    return selected


def choose_packet_cards(fresh,cached,old,target=200):
    selected=choose_new_cards(fresh,old,target)
    return selected+choose_new_cards(cached,old+selected,target-len(selected))


def selected_snapshots(fresh,cached,rows):
    lookup={s['id']:s for s in cached+fresh};wanted={r['snapshot_id'] for r in rows}
    if not wanted<=set(lookup):raise ValueError('selected snapshot missing')
    return [lookup[sid] for sid in sorted(wanted)]


def existing_queue(root,report):
    path=report/'queue-summary.json'
    if not path.exists():return False
    if json.loads(path.read_text())['queue_sha256']!=filehash(root/'queue.jsonl'):
        raise ValueError('saved queue changed')
    return True


def merge_labeled(old,labels,manifest):
    """Append trusted train cards without repartitioning any existing dev data."""
    from .data import validate_rows
    rows=list(old);ids={r['id'] for r in old};inputs={digest(r['input']) for r in old}
    pairs={(r['snapshot_id'],r['document_id']) for r in old}
    for label in labels:
        card=label['card'];key=digest(card['input']);pair=(card['snapshot_id'],card['document_id'])
        if (card['split']!='train' or label['row_id']!=card['id'] or
            key!=label['input_sha256'] or key!=card['input_sha256'] or
            card['id'] in ids or key in inputs or pair in pairs):
            raise ValueError('new label/input/split/duplicate violation')
        source=label.get('resolution',{}).get('source')
        if source not in {'llm_consensus','agent_adjudication'}:
            raise ValueError('new label requires trusted resolution')
        rows.append(dict(card,role='train',label=label['decision']['label'],
                         defect=label['decision']['defect'],label_source=source))
        ids.add(card['id']);inputs.add(key);pairs.add(pair)
    validate_rows(rows,manifest)
    roles=collections.defaultdict(set)
    for row in rows:roles[row['family']].add(row['role'])
    if any(len(v)!=1 for v in roles.values()):raise ValueError('cross-role family')
    return rows


def prepare(args):
    from .live import ROOT,SPLIT,BUDGET_DB,DEEPSEEK,read_jsonl
    from .live_api import utc
    oldbase=ROOT/'artifacts/system-one-pilot/adaptation-v1'
    old=read_jsonl(oldbase/'dataset-v1/dataset.jsonl');manifest=json.loads(SPLIT.read_text())
    tasks=task_plan(manifest,{r['family'] for r in old})
    out=args.report;out.mkdir(parents=True,exist_ok=True)
    p={'version':1,'id':'expansion-20261027','namespace':'expansion-v1','created_at':utc(),
       'tasks':tasks,'task_roles':{t:'train' for t in tasks},'seed':25,'max_steps':80,'max_errors':5,'timeout':900,
       'agent':DEEPSEEK,'simulator':DEEPSEEK,'retrieval':'bm25',
       'train_families':[manifest['tasks'][t]['family'] for t in tasks],
       'calibration_families':[],'validation_families':[],'split_sha256':filehash(SPLIT),
       'old_dataset_sha256':filehash(oldbase/'dataset-v1/dataset.jsonl'),
       'old_trusted_sha256':filehash(oldbase/'trusted-labels-v1.jsonl'),
       'cached_pool_sha256':filehash(oldbase/'pool.jsonl'),
       'daily_limit_nusd':1_000_000_000,'timezone':'Asia/Novosibirsk',
       'series_caps_nusd':{'expansion-v1-collection':200_000_000,'expansion-v1-annotation':750_000_000},
       'target':200,'per_snapshot_max':20,'scope':'train-only engineering packet; no independent validation claim',
       'stop':'full reservation before every request; unknown blocks all roles; no retries',
       'external_data':'selected synthetic banking train scenarios to DeepSeek simulator; observed state/evidence to DeepSeek/Qwen annotators; prior rubric unchanged',
       'budget_ledger':str(BUDGET_DB.relative_to(ROOT)),'root':str(args.root.relative_to(ROOT))}
    if (out/'protocol.json').exists():raise ValueError('protocol already exists; preserve it')
    args.root.mkdir(parents=True,exist_ok=False);write_json(out/'protocol.json',p)
    print(json.dumps({'tasks':tasks,'families':len(tasks),'protocol_sha256':filehash(out/'protocol.json')}))


def run(args):
    from .live import ROOT,BUDGET_DB,collect,extract,annotate,read_jsonl,save_jsonl,SPLIT
    from .live_api import configure_daily_budget,authorize_series,preflight,PaidClient,daily_summary,BudgetError
    p=json.loads((args.report/'protocol.json').read_text())
    if p['root']!=str(args.root.relative_to(ROOT)):raise ValueError('root differs')
    base=ROOT/'artifacts/system-one-pilot/adaptation-v1'
    if p['old_dataset_sha256']!=filehash(base/'dataset-v1/dataset.jsonl') or p['cached_pool_sha256']!=filehash(base/'pool.jsonl'):
        raise ValueError('original data changed')
    configure_daily_budget(BUDGET_DB,p['daily_limit_nusd'],p['timezone'])
    for series,cap in p['series_caps_nusd'].items():authorize_series(BUDGET_DB,series,cap)
    preflight(args.root/'preflight')
    if existing_queue(args.root,args.report):
        annotate(SimpleNamespace(root=args.root,version=2,series='expansion-v1-annotation',namespace='expansion-v1/'))
        return
    collect(SimpleNamespace(root=args.root,plan=args.report/'protocol.json',episodes=len(p['tasks']),series='expansion-v1-collection'))
    # Unknown outcomes must stop the entire packet, even between roles.
    if PaidClient(BUDGET_DB,'expansion-v1-collection').summary()['unresolved']:raise BudgetError('collection unknown stops annotation')
    extract(SimpleNamespace(root=args.root,target=10000,allowed_splits=['train']))
    old=read_jsonl(base/'dataset-v1/dataset.jsonl')
    fresh=read_jsonl(args.root/'pool.jsonl');cached=read_jsonl(base/'pool.jsonl')
    # Family-round-robin plus whole document-snapshot exclusion; no label-based choice.
    selected=choose_packet_cards(fresh,cached,old,p['target'])
    if not selected:raise ValueError('no new admitted train cards')
    # Initial extract selection is retained; final packet has a separate immutable queue.
    (args.root/'queue.jsonl').rename(args.root/'extract-queue.jsonl')
    save_jsonl(args.root/'queue.jsonl',selected)
    snapshots=selected_snapshots(read_jsonl(args.root/'snapshots.jsonl'),read_jsonl(base/'snapshots.jsonl'),selected)
    (args.root/'snapshots.jsonl').rename(args.root/'extract-snapshots.jsonl')
    save_jsonl(args.root/'snapshots.jsonl',snapshots)
    write_json(args.report/'queue-summary.json',{'rows':len(selected),'families':dict(collections.Counter(r['family'] for r in selected)),
        'snapshots':len({r['snapshot_id'] for r in selected}),'queue_sha256':filehash(args.root/'queue.jsonl'),
        'fresh_task_rows':sum(r['task_id'] in p['tasks'] for r in selected),'test_rows':0,
        'scope':p['scope'],'daily_before_annotation':daily_summary(BUDGET_DB)})
    annotate(SimpleNamespace(root=args.root,version=2,series='expansion-v1-annotation',namespace='expansion-v1/'))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['prepare','run'])
    from .live import ROOT
    parser.add_argument('--root',type=Path,default=ROOT/'artifacts/system-one-pilot/expansion-packet-v1')
    parser.add_argument('--report',type=Path,default=ROOT/'experiments/system-one-pilot/results/expansion-20261027')
    args=parser.parse_args();(prepare if args.command=='prepare' else run)(args)


if __name__=='__main__':main()
