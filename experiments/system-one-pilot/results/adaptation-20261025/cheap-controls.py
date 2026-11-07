"""Descriptive controls fixed before new labels; reads only the gated dataset."""
import collections
import json
from pathlib import Path
from scripts.system_one_pilot.adapt_head import hard,load_dataset
from scripts.system_one_pilot.compare import quality
from scripts.system_one_pilot.data import bm25
root=Path(__file__).resolve().parents[4]
report=Path(__file__).resolve().parent
rows=load_dataset(root/'artifacts/system-one-pilot/adaptation-v1/dataset-v1',report/'protocol.json')
train=[r for r in rows if r['role']=='train' and hard(r)]
prior=sum(r['label']=='useful' for r in train)/len(train)
result={'train_prior':prior,'train_hard':len(train),'roles':{},'scope':'descriptive cheap controls; no threshold fit or final test'}
for role in ['train','calibration','validation']:
 subset=[r for r in rows if r['role']==role]
 binary=[r for r in subset if hard(r)]
 pools=collections.defaultdict(list)
 for r in subset:pools[r['snapshot_id']].append(r)
 pairs=[];eligible_pools=0
 for pool in pools.values():
  scores=bm25(pool[0]['input']['state'],[r['input']['candidate'] for r in pool])
  positive=[s for r,s in zip(pool,scores) if hard(r) and r['label']=='useful']
  negative=[s for r,s in zip(pool,scores) if hard(r) and r['label']=='irrelevant']
  if positive and negative:eligible_pools+=1
  pairs.extend(float(p>n)+.5*float(p==n) for p in positive for n in negative)
 result['roles'][role]={'train_prior_metrics':quality([int(r['label']=='useful') for r in binary],[prior]*len(binary)),
  'bm25':{'within_snapshot_auc':sum(pairs)/len(pairs) if pairs else None,'hard_pairs':len(pairs),'selected_pools':len(pools),'eligible_pools':eligible_pools,'probability':False}}
with (report/'cheap-controls.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps(result))
