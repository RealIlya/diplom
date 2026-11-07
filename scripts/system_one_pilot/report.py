"""Read-only pilot summary; never treats technical failures as semantic labels."""
import argparse
import collections
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path

from .data import digest,write_json
from .cli import filehash
from .live import DEFAULT_RUN,BUDGET_DB,SPLIT,read_jsonl,code_manifest
from .live_api import PaidClient,connect,utc


def annotation_summary(records):
    valid=[r for r in records if r['status']=='valid']
    groups=collections.defaultdict(list)
    for r in records:groups[r['row_id']].append(r)
    pairs=[g for g in groups.values() if len(g)==2 and all(r['status']=='valid' for r in g)]
    return {'responses':len(records),'statuses':dict(collections.Counter(r['status'] for r in records)),
        'by_model':{m:dict(collections.Counter(r['status'] for r in records if r['model']==m)) for m in sorted({r['model'] for r in records})},
        'valid_labels':dict(collections.Counter(r['annotation']['label'] for r in valid)),
        'technical_errors':dict(collections.Counter(r.get('error') for r in records if r['status']!='valid')),
        'pairs_with_two_valid_answers':len(pairs),
        'same_label_pairs':sum(g[0]['annotation']['label']==g[1]['annotation']['label'] for g in pairs),
        'different_label_pairs':sum(g[0]['annotation']['label']!=g[1]['annotation']['label'] for g in pairs),
        'uncertain_pairs':sum(any(r['annotation']['label']=='uncertain' for r in g) for g in pairs),
        'model_defect_pairs':sum(any(r['annotation'].get('defect') for r in g) for g in pairs)}


def cost_summary(rows):
    reported=Decimal(0);unknown=0;tokens=collections.Counter();missing=collections.Counter()
    for row in rows:
        response=json.loads(row['response']) if row['response'] else {}
        usage=response.get('usage') or {}
        if row['actual_nusd'] is None:unknown+=1
        else:reported+=Decimal(str(usage['cost']))
        for field in ['prompt_tokens','completion_tokens']:
            if usage.get(field) is not None:tokens[field]+=usage[field]
            else:missing[field]+=1
        for name,field in [('prompt_tokens_details','cached_tokens'),('completion_tokens_details','reasoning_tokens')]:
            value=(usage.get(name) or {}).get(field)
            if value is None:missing[field]+=1
            else:tokens[field]+=value
    return {'calls':len(rows),'reported_usage_cost_usd_exact':format(reported,'f'),
        'budget_charged_or_held_usd':sum(r['actual_nusd'] if r['actual_nusd'] is not None else r['reserved_nusd'] for r in rows)/1e9,
        'unknown_actual_cost_calls':unknown,'reported_token_counters':dict(tokens),
        'missing_token_counter_calls':dict(missing),'token_note':'API-reported counters; reasoning may use a different tokenizer and is not added to completion_tokens'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=DEFAULT_RUN)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();root=args.root.resolve()
    queue=read_jsonl(root/'queue.jsonl');admission=json.loads((root/'admission.json').read_text())
    for row in queue:assert digest(row['input'])==row['input_sha256']
    episodes=[]
    for path in sorted((root/'trajectories').glob('*.json')):
        row=json.loads(path.read_text())
        episodes.append({'task_id':row['task_id'],'status':row['status'],'messages':len(row['native']['messages']),
            'termination_reason':row['native'].get('termination_reason'),'error':row.get('error'),
            'wall_seconds':(datetime.fromisoformat(row['finished_at'])-datetime.fromisoformat(row['started_at'])).total_seconds(),
            'source':str(path.relative_to(root)),'sha256':filehash(path)})
    labels={}
    for version,folder in [('v1','annotations'),('v2','annotations-v2')]:
        records=[json.loads(p.read_text()) for p in sorted((root/folder).glob('*.json'))]
        labels[version]=annotation_summary(records)
    with connect(BUDGET_DB) as db:
        costs={series:cost_summary([dict(r) for r in db.execute('SELECT * FROM api_calls WHERE series=?',(series,))]) for series in ['collection','annotation']}
        receipts=[dict(r) for r in db.execute('SELECT * FROM api_reconciliations ORDER BY at')]
    human={'cards':0,'confirmed':0}
    if (root/'pilot.sqlite3').exists():
        from .review import ReviewStore
        store=ReviewStore(root/'pilot.sqlite3');items=store.queue()
        human={'cards':len(items),'statuses':dict(collections.Counter(r['status'] for r in items)),
               'human_confirmed':sum(r['status']=='confirmed' for r in items),
               'trusted_accepted':sum(r['status']=='accepted' for r in items),
               'kinds':dict(collections.Counter(r['kind'] for r in items)),
               'required':sum(r['required'] for r in items),'blind_control_seed':25,
               'blind_control_ids':[r['id'] for r in items if r['kind']=='control']}
    ready=human['cards']==len(queue) and labels['v2']['responses']==2*len(queue)
    status='trusted_labels_ready' if ready and human.get('trusted_accepted',0)+human.get('human_confirmed',0)==len(queue) else 'ready_for_human_review' if ready else 'in_progress'
    report={'at':utc(),'status':status,
        'run_root':str(root),'versions':code_manifest(),'split_sha256':filehash(SPLIT),
        'episodes':episodes,'user_stop_dialogues':sum(e['termination_reason']=='user_stop' for e in episodes),
        'admission':{'document_snapshot_pairs':admission['pool_document_snapshots'],'counts_4096':admission['counts'],
            'raw_counts':{limit:dict(collections.Counter(r['lengths'][limit]['status'] for r in admission['rows'])) for limit in ['1024','4096','8192']},
            'selected_cards':len(queue),'selected_tasks':sorted({r['task_id'] for r in queue}),
            'selected_families':len({r['family'] for r in queue}),'selected_snapshots':len({r['snapshot_id'] for r in queue})},
        'annotations':labels,'human_review':human,'costs':costs,'reconciliation_receipts':receipts,
        'budgets':{s:PaidClient(BUDGET_DB,s).summary() for s in ['collection','annotation']},
        'runtime':json.loads((root/'runtime-4096-mps.json').read_text()),
        'artifacts':{str(p.relative_to(root)):filehash(p) for p in sorted(root.rglob('*')) if p.is_file() and p.suffix in {'.json','.jsonl'}},
        'scientific_quality':f"not measured; human confirmations: {human.get('human_confirmed',0)}; no adaptation; native ENV is not full agent reward"}
    write_json(args.out,report)
    print(json.dumps({'status':report['status'],'summary':str(args.out.resolve()),'human':human}))


if __name__=='__main__':main()
