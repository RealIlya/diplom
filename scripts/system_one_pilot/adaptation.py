"""Frozen expansion plan and family-separated dataset; reuses the pilot pipeline."""
import argparse
import collections
import json
from pathlib import Path
from .data import digest,write_json
from .live_data import select_cards
from .compare import filehash


def make_plan(manifest,old_tasks,exposed_dev,train_families=5,seed=25):
    if digest({k:v for k,v in manifest.items() if k!='manifest_sha256'})!=manifest['manifest_sha256']:
        raise ValueError('split manifest changed')
    tasks=manifest['tasks'];old_families={tasks[t]['family'] for t in old_tasks}
    groups=collections.defaultdict(list)
    for tid,v in tasks.items():
        if v['split'] in {'train','dev'}:groups[(v['split'],v['family'])].append(tid)
    dev=sorted({f for sp,f in groups if sp=='dev'},key=lambda f:digest([seed,f]))
    if len(dev)!=5 or not set(exposed_dev)<=set(dev) or len(exposed_dev)>2:raise ValueError('unexpected dev families')
    calibration=list(sorted(exposed_dev));calibration += [f for f in dev if f not in calibration][:2-len(calibration)]
    validation=[f for f in dev if f not in calibration]
    train=sorted({f for sp,f in groups if sp=='train' and f not in old_families},key=lambda f:digest([seed,f]))[:train_families]
    if len(train)!=train_families:raise ValueError('not enough train families')
    selected=[];task_queues=[]
    for sp,f in sorted([('train',f) for f in train]+[('dev',f) for f in dev],key=lambda x:digest([seed,*x])):
        ordered=sorted(groups[(sp,f)],key=lambda t:digest([seed,f,t]))[:1 if sp=='train' else 2]
        task_queues.append(ordered)
    for i in range(2):
        selected.extend(q[i] for q in task_queues if len(q)>i)
    return {'version':2,'namespace':'adaptation-v1','tasks':selected,'seed':seed,
            'train_families':train,'calibration_families':calibration,'validation_families':validation,
            'task_roles':{t:('train' if tasks[t]['split']=='train' else 'calibration' if tasks[t]['family'] in calibration else 'validation') for t in selected},
            'max_steps':80,'max_errors':5,'timeout':900,'retrieval':'bm25'}


def select_family_cards(rows,target=100,per_family=10):
    groups=collections.defaultdict(list)
    for r in rows:groups[r['family']].append(r)
    buckets=[select_cards(groups[f],target=per_family) for f in sorted(groups,key=lambda f:digest([25,f]))]
    selected=[]
    while len(selected)<target and any(buckets):
        for b in buckets:
            if b and len(selected)<target:selected.append(b.pop(0))
    return selected


def partition_cards(cards,plan):
    result={'train':[],'calibration':[],'validation':[]};seen={};family_roles={}
    for c in cards:
        if c['split']=='test':raise ValueError('test forbidden')
        if c['split']=='train':role='train'
        elif c['family'] in plan['calibration_families']:role='calibration'
        elif c['family'] in plan['validation_families']:role='validation'
        else:raise ValueError('unknown dev family')
        identity=digest(c['input'])
        if identity in seen or c['family'] in family_roles and family_roles[c['family']]!=role:
            raise ValueError('input/family overlap')
        seen[identity]=role;family_roles[c['family']]=role
        result[role].append(dict(c,role=role))
    return result


def verify_collection_plan(path):
    from .live import SPLIT,TAU
    p=json.loads(Path(path).read_text());m=json.loads(SPLIT.read_text())
    if p['split_sha256']!=filehash(SPLIT) or digest({k:v for k,v in m.items() if k!='manifest_sha256'})!=m['manifest_sha256']:
        raise ValueError('collection split changed')
    if len(p['tasks'])!=len(set(p['tasks'])):raise ValueError('duplicate collection task')
    source=json.loads(SPLIT.with_name('source-manifest.json').read_text())
    for name,sha in source['files'].items():
        if '/tasks/' not in name and filehash(TAU/name)!=sha:raise ValueError('pinned source changed')
    for tid in p['tasks']:
        v=m['tasks'][tid]
        if v['split'] not in {'train','dev'}:raise ValueError('test forbidden')
        expected='train' if v['split']=='train' else 'calibration' if v['family'] in p['calibration_families'] else 'validation'
        if p['task_roles'][tid]!=expected:raise ValueError('collection role changed')
        task=TAU/'data/tau2/domains/banking_knowledge/tasks'/(tid+'.json')
        if digest(json.loads(task.read_text()))!=m['task_hashes'][tid]:raise ValueError('selected task changed')
    return p


def prepare(args):
    from .live import SPLIT,ROOT,DEEPSEEK,BUDGET_DB
    from .live_api import PaidClient,utc
    m=json.loads(SPLIT.read_text());old=json.loads((ROOT/'artifacts/system-one-pilot/api-v1/collection-plan.json').read_text())
    plan=make_plan(m,old['tasks'],{m['tasks']['task_023']['family']})
    plan.update(id='head-adaptation-v1',created_at=utc(),split_sha256=filehash(SPLIT),agent=DEEPSEEK,simulator=DEEPSEEK,
        frozen_export='artifacts/system-one-pilot/api-v1/exports/trusted-labels-v1.jsonl',
        frozen_export_sha256='e23dde49988d770ad4602a3dcc7730ed13c4bc5c4c791b77a676b32f13e579d0',
        selection={'target':100,'per_family':10,'max_snapshots_per_episode':3,'profile':4096},
        model={'arm':'kev-0.8b','adaptation':'head only; original BF16 backbone and merged LoRA frozen',
               'checkpoint_revision':'9a45d25eb2ab761841196625383fa1dff0e56c1e'},
        training={'optimizer':'AdamW','lr':1e-4,'weight_decay':.01,'batch_size':16,'epochs':20,'seed':25,'losses':['ce','brier'],
                  'select_epoch':'fixed last','hpo':False,'threshold':.5,'temperature_grid':[.5,1,2,2.3510958125672174,3,4,6,8]},
        gates={'train_hard_min':40,'train_families_min':6,'calibration_families_min':2,'validation_families_min':3,'validation_hard_min':15},
        spending_before={series:PaidClient(BUDGET_DB,series).summary() for series in ['collection','annotation']},
        cost_estimate={'collection_13_episodes_historical_usd':.133,'collection_original_scenario_range_usd':[.936,4.68],
                       'annotation_100_pairs_historical_usd':.1547,'annotation_scenario_x2_usd':.31,
                       'stop':'persistent common caps collection$1/annotation$0.50 including prior calls; unknown blocks, no retry'},
        online={'arms':['native','bm25','llm','frozen','ce','brier'],'tasks':'one first-hash task per validation family',
                'seed':25,'max_steps':80,'evaluation':'ALL using native reward_basis; DeepSeek judge, no default model calls',
                'pack_tokens':4096,'threshold':.5,'fallback':'LLM selector on local error/overflow or no selected evidence; retained BM25 on invalid selector result',
                'quality_scope':'small paired dev pilot, no test or claim of statistical significance'},
        test_access=False,training_budget_gpu_rub=0)
    if filehash(ROOT/plan['frozen_export'])!=plan['frozen_export_sha256']:raise ValueError('old labels changed')
    write_json(args.out,plan)
    print(json.dumps({k:plan[k] for k in ['tasks','train_families','calibration_families','validation_families']}))


def dataset(args):
    from .live import ROOT,read_jsonl,save_jsonl
    p=json.loads(args.protocol.read_text());old=ROOT/p['frozen_export']
    if filehash(old)!=p['frozen_export_sha256']:raise ValueError('old export changed')
    from .data import validate_rows
    from .live import SPLIT
    new=read_jsonl(args.labels)
    if any(r['card']['task_id'] not in p['tasks'] for r in new):raise ValueError('unplanned new task')
    cards=[]
    for r in read_jsonl(old)+new:
        c=r['card'];label=r['decision']['label']
        if digest(c['input'])!=r['input_sha256'] or label not in {'useful','irrelevant','uncertain'}:raise ValueError('label input changed')
        # defect is separate from semantic uncertainty and never enters supervised loss.
        cards.append(dict(c,label=label,defect=r['decision'].get('defect',False),label_source=r.get('resolution',{}).get('source','human')))
    validate_rows(cards,json.loads(SPLIT.read_text()))
    partitions=partition_cards(cards,p);stats={}
    for role,rs in partitions.items():
        hard=[r for r in rs if r['label']!='uncertain' and not r['defect']]
        stats[role]={'rows':len(rs),'hard':len(hard),'families':len({r['family'] for r in hard}),
                     'labels':dict(collections.Counter(r['label'] for r in hard))}
    g=p['gates'];errors=[]
    for role,minimum in [('train',g['train_hard_min']),('validation',g['validation_hard_min'])]:
        if stats[role]['hard']<minimum:errors.append(role+' insufficient hard rows')
    for role in partitions:
        if stats[role]['families']<g[role+'_families_min']:errors.append(role+' insufficient families')
        if set(stats[role]['labels'])!={'useful','irrelevant'}:errors.append(role+' needs both hard classes')
    args.out.mkdir(parents=True,exist_ok=False)
    save_jsonl(args.out/'dataset.jsonl',[r for rs in partitions.values() for r in rs])
    write_json(args.out/'manifest.json',{'protocol_sha256':filehash(args.protocol),'dataset_sha256':filehash(args.out/'dataset.jsonl'),
        'old_labels_sha256':filehash(old),'new_labels_sha256':filehash(args.labels),'stats':stats,'gates_passed':not errors,'errors':errors})
    print(json.dumps({'stats':stats,'errors':errors}))
    if errors:raise ValueError('dataset gates failed; no training')


def main():
    p=argparse.ArgumentParser();s=p.add_subparsers(required=True)
    a=s.add_parser('prepare');a.add_argument('--out',type=Path,required=True);a.set_defaults(func=prepare)
    a=s.add_parser('dataset');a.add_argument('--protocol',type=Path,required=True);a.add_argument('--labels',type=Path,required=True);a.add_argument('--out',type=Path,required=True);a.set_defaults(func=dataset)
    a=p.parse_args();a.func(a)

if __name__=='__main__':main()
